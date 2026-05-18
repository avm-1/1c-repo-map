# Инструкция: публикация на GitHub

## Шаг 1: Создание Personal Access Token (PAT)

1. Зайдите на [github.com/settings/tokens](https://github.com/settings/tokens)
2. Нажмите **Generate new token (classic)**
3. В поле **Note** напишите: `1c-repo-map publish`
4. Время жизни (**Expiration**): выберите 7 дней (или 30 дней)
5. Права (**Scopes**): отметьте только:
   - ✅ `repo` — полный доступ к репозиториям (или `public_repo` — только публичные)
6. Нажмите **Generate token** внизу страницы
7. **Скопируйте токен сразу** — он показывается только один раз!

Токен выглядит примерно так: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Шаг 2: Создание репозитория на GitHub

1. Зайдите на [github.com/new](https://github.com/new)
2. **Repository name**: `1c-repo-map`
3. **Description**: `Репозиторные карты для конфигураций 1С. Сокращает расход токенов LLM на 80-90%`
4. Выберите **Public**
5. **Не создавайте** README, .gitignore и license — они уже есть в локальном репозитории
6. Нажмите **Create repository**

## Шаг 3: Пуш локального репозитория

В PowerShell выполните:

```powershell
$env:PATH = "C:\temp\git\bin;" + $env:PATH
cd "C:\Users\amak\Desktop\Задачи\2.Тест_поиск\1c-repo-map"
git push -u origin main
```

Git запросит логин и пароль:
- **Username**: ваш логин GitHub (`avm-1`)
- **Password**: вставьте скопированный **Personal Access Token** (НЕ пароль от GitHub!)

Готово! Репозиторий опубликован.

## Альтернатива: пуш через URL с токеном

Если интерактивный ввод не работает:

```powershell
$env:PATH = "C:\temp\git\bin;" + $env:PATH
cd "C:\Users\amak\Desktop\Задачи\2.Тест_поиск\1c-repo-map"
$token = "ghp_ВАШ_ТОКЕН"
git push https://"$token"@github.com/avm-1/1c-repo-map.git main
```

## Проверка

Откройте [github.com/avm-1/1c-repo-map](https://github.com/avm-1/1c-repo-map) — вы должны увидеть все файлы.
