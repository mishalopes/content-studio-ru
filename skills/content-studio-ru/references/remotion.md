# Remotion

Официальные инструкции: https://github.com/remotion-dev/skills
Документация движка: https://www.remotion.dev/docs
Открывать нужный раздел под задачу; исходники движка и его навыки в пакет не входят.

В существующем проекте определить версию по package.json и lock-файлу.
Для новой функции сверить API с официальной документацией соответствующей версии.
Для нового проекта подобрать совместимые зависимости, сохранить версии и lock-файл.
Следовать запросу пользователя на превью или готовый файл.

Типовые команды для подготовленного проекта

```bash
npx remotion studio --no-open
npx remotion compositions src/index.ts
npx remotion still src/index.ts Main out/cover.png --frame=30
npx remotion render src/index.ts Main out/reel.mp4 --codec=h264
```

Пути и ID Main заменить реальными значениями. После сборки проверить субтитры,
синхронность, кириллицу, медиа и кадры на границах сцен. Инструкции Remotion
распространяются под MIT. Лицензирование видеодвижка и сервисов проверять
по https://www.remotion.dev/docs/license.
