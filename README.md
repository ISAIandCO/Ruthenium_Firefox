# RFirefox for Android

![Иконка RFirefox: стандартный Firefox с отметкой R](branding/android/rfirefox-xxxhdpi.webp)

Независимая Android-сборка стабильного Firefox с ограниченной поддержкой
`Russian Trusted Root CA`. Дополнительный корень принимается только при
проверке HTTPS-серверов и только для DNS-имён в зонах `.ru`, `.рф`
(`.xn--p1ai`) и `.su`.

Проект не является форком всего дерева Firefox. В репозитории хранятся
проверяемый сертификат, скрипты патчирования, тесты и GitHub Actions. При каждом
релизном запуске workflow получает свежий стабильный исходный changeset Mozilla,
накладывает патч и собирает отдельное Android-приложение.

> [!IMPORTANT]
> Проект не связан с Mozilla, командой Ruthenium Chromium или Минцифры России.
> Добавление центра сертификации меняет модель доверия браузера. Используйте
> сборку только если понимаете последствия и доверяете исходникам и CI этого
> репозитория.

## Что именно изменено

| Область | Изменение |
|---|---|
| Дополнительный CA | В Gecko встраивается закреплённая копия `Russian Trusted Root CA` |
| Назначение доверия | Корень добавляется только для `VerifyUsage::TLSServer`; проверки клиентских и почтовых сертификатов не изменяются |
| Ограничение имён | При построении цепочки `mozilla::pkix` получает RFC 5280 Name Constraints: разрешены `.ru`, `.xn--p1ai`, `.su` |
| IP-адреса | Для цепочек через добавленный корень запрещены все IPv4- и IPv6-SAN |
| Обычная PKI-проверка | Проверки имени хоста, подписей, срока, EKU и отзыва Firefox остаются включёнными |
| Android-пакет | `applicationId` изменён на `app.ruthenium.firefox`, поэтому приложение устанавливается отдельно от официального Firefox |
| Брендинг приложения | Имя приложения — `RFirefox`, deep-link scheme — `ruthenium`, shared user ID — `app.ruthenium.firefox.sharedID` |
| Иконка | Стандартная иконка Firefox сохраняется, в левом нижнем углу добавляется белая отметка `R` |
| Релиз | Release-вариант Fenix подписывается фиксированным публичным debug-ключом из репозитория и публикуется с суффиксом `_debug` |

Патч изменяет в полученном дереве Mozilla следующие файлы:

- `security/certverifier/CertVerifier.h` и `.cpp` — отдельный список корней
  только для TLS server verification;
- `security/certverifier/NSSCertDBTrustDomain.h` и `.cpp` — передача
  дополнительных Name Constraints при построении цепочки;
- `security/certverifier/RutheniumRoot.h` — генерируемые DER-массивы корня и
  ограничений;
- `mobile/android/fenix/app/build.gradle` — независимый application ID,
  shared user ID и deep-link scheme;
- `mobile/android/fenix/app/src/main/res/values/static_strings.xml` и release-
  вариант файла — имя приложения;
- `mobile/android/fenix/app/src/main/res/drawable/ic_launcher_foreground.xml`,
  release-foreground, monochrome VectorDrawable и release WebP по всем Android
  density — отметка `R` поверх штатной иконки Firefox.

Готовые normal/round legacy-ресурсы находятся в `branding/android/`. Для
adaptive и themed icon патчер оставляет исходные Mozilla-векторы без изменений
и дописывает отдельный векторный слой `R`, поэтому отметка сохраняется при
маскировании Android. Альтернативные иконки встроенной функции выбора Fenix не
изменяются.

Скрипт `scripts/patch_firefox.py` применяет каждую замену только при однозначном
совпадении ожидаемого upstream-кода. Если Mozilla изменила соответствующий
участок, патч завершается ошибкой вместо молчаливой сборки с неполной политикой.

## Граница доверия сертификату

Сертификат хранится в `certificates/russian_trusted_root_ca.pem`. Перед генерацией
C++-заголовка проверяется его DER SHA-256:

```text
d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31
```

Ожидаемый хэш и две исходные ссылки закреплены в
`certificates/ministry-ca-lock.json`. Сетевой сертификат во время сборки не
скачивается: используется проверенная копия из репозитория. Несовпадение хэша
останавливает патч.

Ограничения относятся только к цепочке, построенной через этот дополнительный
корень. Они не сужают обычное хранилище Mozilla. Сертификат также не добавляется
в системное хранилище Android и не даёт другим приложениям нового доверия.

## Выбор стабильных исходников

`https://hg-edge.mozilla.org/mozilla-central` — основное дерево разработки
Mozilla и источник Firefox Nightly. Его `tip` не равен последнему стабильному
Firefox, поэтому непосредственно собирать `tip` и называть результат stable
нельзя.

`scripts/resolve_firefox_source.py` выполняет строгую последовательность:

1. читает `LATEST_FIREFOX_VERSION` из официального Firefox Product Details;
2. строит имя Android-тега вида `FIREFOX-ANDROID_153_0_4_RELEASE`;
3. находит ровно этот тег в официальной release-ветке
   `https://hg-edge.mozilla.org/releases/mozilla-release`;
4. проверяет 40-символьный Mercurial changeset и скачивает архив именно этой
   ревизии;
5. после распаковки сверяет `browser/config/version.txt` с выбранной версией.

Таким образом, код остаётся кодом официального монорепозитория Firefox
(GeckoView, Fenix и Android Components), но берётся из стабилизированной ветки,
а не из движущегося Nightly tip. При отсутствии согласованного release-тега
сборка останавливается.

## Автоматизация и релизы

В репозитории два независимых workflow:

| Workflow | Триггер | Что делает |
|---|---|---|
| `Validate Ruthenium patches` | push в `main`, pull request или ручной запуск | Запускает быстрые unit-тесты, определяет стабильный тег и проверяет, что все точки патча существуют в текущем upstream; Firefox не собирает |
| `Build and release RFirefox for Android` | только ручной запуск и расписание | Скачивает выбранный stable changeset, собирает GeckoView/Fenix с debug signing, проверяет APK и создаёт GitHub Release |

Полная сборка **не запускается после изменения файлов или push**. Вручную её
можно запустить на вкладке **Actions → Build and release RFirefox for Android →
Run workflow**.

Автоматический запуск назначен на 15-е число каждого месяца в 03:17 UTC. Перед
дорогой сборкой workflow проверяет GitHub Releases. Если debug-релиз текущей
версии Firefox уже существует, запуск успешно завершается без скачивания и компиляции.
Это защищает от повторной публикации одной версии. Если патчи изменились после
публикации, существующий релиз и его тег следует осознанно удалить перед ручной
пересборкой либо дождаться следующей версии Firefox.

Для новой версии workflow создаёт:

- Git tag из версии Firefox с суффиксом, например `153.0.4_debug`;
- GitHub Release с точно таким же именем `153.0.4_debug`;
- устанавливаемый APK, подписанный закреплённым debug-ключом;
- соседний файл `.sha256` для каждого APK;
- `build-info.txt` с upstream-тегом, changeset и параметрами патча.

Подход «собрать артефакты, затем опубликовать GitHub Release» взят за ориентир
из release workflow NekoBox. Здесь вместо скачиваемого стороннего `ghr`
используется предустановленный GitHub CLI, а подпись APK проверяется через
Android `apksigner` до публикации.

## Фиксированный публичный debug-ключ

Secrets не требуются. Keystore `signing/rfirefox-debug.keystore` намеренно
добавлен в репозиторий и используется всеми локальными и GitHub Actions
debug-релизами. Параметры стандартные для Android debug signing:

- alias: `androiddebugkey`;
- пароль keystore: `android`;
- пароль ключа: `android`;
- SHA-256 сертификата:
  `d7a19050129bbb6e7af6f29dc899a123757ca226ea0ee3c7395c43527592035f`.

Workflow передаёт абсолютный путь к файлу через `RFIREFOX_DEBUG_KEYSTORE`, патч
явно назначает его `signingConfigs.debug`, а затем проверяет сертификат готового
APK через `apksigner`. Ожидаемые параметры также записаны в
`signing/debug-key-lock.json`.

Один и тот же ключ позволяет устанавливать следующие `_debug`-версии поверх
предыдущих. Однако это не защищённая release-подпись: приватный ключ и пароли
видны всем. Любой человек может подписать этим ключом изменённый APK, который
Android примет как обновление RFirefox. Ключ нельзя использовать для production.

## Установка и обновление

1. Откройте раздел **Releases** и выберите нужную версию Firefox.
2. Скачайте APK и одноимённый `.sha256`.
3. Проверьте файл, например `sha256sum -c <имя-apk>.sha256`.
4. Разрешите Android установку из выбранного источника и откройте APK либо
   выполните `adb install <имя-apk>`.

Следующие `_debug`-релизы устанавливаются поверх предыдущих, поскольку workflow
использует один закреплённый keystore. При будущем переходе на закрытый
production release-ключ текущую debug-сборку потребуется удалить: Android не
разрешает смену сертификата подписи обычным обновлением.

## Локальная проверка патчей

Быстрые тесты и определение текущего стабильного источника:

```bash
python3 -m unittest discover -v
python3 scripts/resolve_firefox_source.py --format json
```

Проверка точек патча на удалённом release-теге без скачивания всего архива:

```bash
python3 scripts/patch_firefox.py \
  --check-remote \
  https://hg-edge.mozilla.org/releases/mozilla-release/raw-file/FIREFOX-ANDROID_153_0_4_RELEASE
```

Применение к уже полученному исходному дереву:

```bash
python3 scripts/patch_firefox.py --source /path/to/firefox-source
```

Полная сборка Firefox может потребовать 8+ CPU, 32 ГБ RAM, около 100 ГБ
свободного SSD и несколько часов. GitHub workflow ограничен шестью часами и
чистит только известные крупные каталоги одноразового GitHub-hosted runner.

## Ограничения и риски

- Это не официальный Firefox и не результат аудита Mozilla.
- Патч покрыт unit-тестами и fail-closed проверками якорей, но полноценная
  интеграционная TLS-матрица на реальных цепочках ещё должна быть добавлена.
- Сборка не является воспроизводимой побитово: toolchain и часть зависимостей
  устанавливаются Mozilla bootstrap/Gradle во время job.
- Основная launcher-иконка намеренно основана на стандартной иконке Firefox с
  добавленной отметкой `R`; в интерфейсе и альтернативных иконках также остаются
  товарные знаки Firefox. Перед широким публичным распространением нужна
  проверка Mozilla Trademark Guidelines.
- Публичный debug-ключ обеспечивает техническую совместимость обновлений, но не
  подтверждает издателя: подписать совместимое обновление может любой владелец
  копии репозитория. Это осознанное временное ограничение.

## Источники и референсы

- [Ruthenium for Android](https://github.com/rutheniumteam/ruthenium-android) —
  исходный Chromium-проект и референс идеи ограниченного доверия;
- [статья на Habr](https://habr.com/ru/articles/1070548/) — описание задачи и
  мотивации;
- [Mozilla `mozilla-central`](https://hg-edge.mozilla.org/mozilla-central) —
  основное development-дерево;
- [Mozilla `mozilla-release`](https://hg-edge.mozilla.org/releases/mozilla-release) —
  источник точного stable changeset;
- [Firefox Product Details](https://product-details.mozilla.org/1.0/firefox_versions.json) —
  официальный номер актуального стабильного Firefox;
- [Firefox for Android source docs](https://firefox-source-docs.mozilla.org/mobile/android/) и
  [сборка Fenix](https://firefox-source-docs.mozilla.org/mobile/android/fenix.html);
- [Russian Trusted Root CA (PEM)](https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt) —
  первичный источник сертификата;
- [RFC 5280, Name Constraints](https://www.rfc-editor.org/rfc/rfc5280#section-4.2.1.10) —
  формат ограничений имён;
- [NekoBox_SF release workflow](https://github.com/ISAIandCO/NekoBox_SF/blob/main/.github/workflows/android-release-to-github-release.yml) —
  референс схемы публикации артефактов;
- [Mozilla Trademark Guidelines](https://www.mozilla.org/foundation/trademarks/policy/).

## Лицензия и уведомления

Код этого репозитория распространяется по MPL-2.0. Исходный код Firefox имеет
MPL-2.0 и другие лицензии, перечисленные в его дереве. Дополнительные юридические
уведомления находятся в `NOTICE.md`. Firefox и логотип Firefox являются
товарными знаками Mozilla Foundation.
