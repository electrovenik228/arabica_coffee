# Настройка CI/CD для проекта Arabica Coffee

## Что уже создано

### 1. GitHub Actions Workflows

**`.github/workflows/ci.yml`** - Continuous Integration
- Запускается при push/PR в ветки `main` и `develop`
- Создает среду с PostgreSQL и Redis
- Устанавливает зависимости
- Проверяет форматирование кода (black)
- Проверяет линтинг (flake8)
- Запускает тесты
- Генерирует отчет о покрытии кода

**`.github/workflows/cd.yml`** - Continuous Deployment
- Запускается при push в `main` или создании тегов `v*.*.*`
- Собирает Docker образ
- Пушит образ в GitHub Container Registry (GHCR)
- Деплоит на сервер через SSH

### 2. Улучшенный Dockerfile
- Использует `python:3.11-slim` для меньшего размера
- Устанавливает системные зависимости
- Оптимизированная кэширование слоев
- Готов к production

## Что нужно настроить

### Шаг 1: Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
SECRET_KEY=your-actual-secret-key
DEBUG=False
DATABASE_URL=postgres://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
```

### Шаг 2: Настройка GitHub Secrets

Для работы CD необходимо добавить следующие secrets в репозиторий:

1. Перейдите в **Settings > Secrets and variables > Actions**
2. Добавьте:

| Secret Name | Description | Пример |
|-------------|-------------|---------|
| `DEPLOY_HOST` | IP адрес или домен сервера | `123.45.67.89` |
| `DEPLOY_USER` | Имя пользователя для SSH | `deploy` |
| `DEPLOY_SSH_KEY` | Приватный SSH ключ | `-----BEGIN RSA PRIVATE KEY-----...` |

**Как получить SSH ключ:**
```bash
# На локальной машине
ssh-keygen -t rsa -b 4096 -f ~/.ssh/arabica_deploy
# Публичный ключ (~/.ssh/arabica_deploy.pub) добавьте в ~/.ssh/authorized_keys на сервере
# Приватный ключ (~/.ssh/arabica_deploy) скопируйте как DEPLOY_SSH_KEY
```

### Шаг 3: Настройка сервера для деплоя

На сервере (куда будет деплоиться приложение):

1. Установите Docker и Docker Compose:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

2. Создайте директорию для проекта:
```bash
sudo mkdir -p /var/www/arabica_coffee
sudo chown -R $USER:$USER /var/www/arabica_coffee
```

3. Склонируйте репозиторий:
```bash
cd /var/www/arabica_coffee
git clone <your-repo-url> .
```

4. Настройте `.env` файл на сервере (см. Шаг 1)

5. Убедитесь, что `docker-compose.yml` настроен правильно

### Шаг 4: Запуск CI/CD

#### Для тестирования CI:
```bash
# Создайте ветку develop если ее нет
git checkout -b develop
git add .
git commit -m "Add CI/CD configuration"
git push origin develop
```

CI запустится автоматически. Проверьте статус в **Actions** на GitHub.

#### Для деплоя на production:
```bash
git checkout main
git merge develop
git tag v1.0.0
git push origin main --tags
```

CD запустится автоматически после push в `main` или создании тега.

### Шаг 5: Мониторинг

1. **GitHub Actions** - статус пайплайнов
2. **GitHub Container Registry** - собранные образы
3. **Сервер** - логи контейнеров:
```bash
docker-compose logs -f
docker-compose ps
```

## Дополнительные настройки (опционально)

### Настройка Codecov для покрытия кода

1. Зарегистрируйтесь на [codecov.io](https://codecov.io)
2. Добавьте `CODECOV_TOKEN` в GitHub Secrets
3. Раскомментируйте секцию в `ci.yml`

### Настройка Slack/Telegram уведомлений

Добавьте шаг в workflow для отправки уведомлений о статусе.

## Возможные проблемы и решения

### 1. Ошибка подключения к базе данных в CI
Убедитесь, что `DATABASE_URL` правильно задан в workflow.

### 2. Ошибка с миграциями
Добавьте шаг `python manage.py migrate` перед тестами в CI.

### 3. Ошибка с статическими файлами
Убедитесь, что в настройках Django указан правильный `STATIC_ROOT`.

### 4. SSH подключение не работает
Проверьте:
- Правильность SSH ключа
- Доступ пользователя к серверу
- Включен ли SSH на сервере (`systemctl status ssh`)

## Структура файлов

```
arabica_coffee/
├── .github/
│   └── workflows/
│       ├── ci.yml          # CI пайплайн
│       └── cd.yml          # CD пайплайн
├── Dockerfile              # Образ для production
├── docker-compose.yml      # Оркестрация контейнеров
├── requirements.txt        # Зависимости Python
├── manage.py              # Django management
├── apps/                  # Django приложения
└── arabica/              # Настройки проекта
```

## Команды для ручного управления

```bash
# Локальный запуск
docker-compose up -d
docker-compose down
docker-compose logs -f django

# Пересборка
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Очистка
docker system prune -a
docker volume prune
```

## Следующие шаги

1. ✅ Созданы workflow файлы
2. ✅ Dockerfile улучшен
3. ⬜ Настроить GitHub Secrets
4. ⬜ Настроить сервер
5. ⬜ Протестировать CI (push в develop)
6. ⬜ Протестировать CD (merge в main)
7. ⬜ Настроить мониторинг и уведомления

## Поддержка

При возникновении проблем:
1. Проверьте логи GitHub Actions
2. Проверьте логи Docker контейнеров на сервере
3. Убедитесь, что все переменные окружения заданы
4. Проверьте сетевую доступность сервера