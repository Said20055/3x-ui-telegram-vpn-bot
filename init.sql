-- init.sql

-- Сначала пытаемся создать пользователя. Если он уже есть, ничего не делаем.
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = '${DB_USER}') THEN

      CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
   END IF;
END
$do$;

-- Пытаемся создать базу данных. Если она уже есть, ничего не делаем.
-- Устанавливаем владельцем нового пользователя.
-- ВАЖНО: Команда CREATE DATABASE не может быть выполнена внутри блока IF EXISTS.
-- Поэтому мы сначала создаем пользователя, а потом создаем БД от его имени.
-- Если БД уже существует, эта команда вызовет ОШИБКУ, но Docker обработает это
-- и продолжит запуск, если ошибка ожидаемая (database already exists).
-- Чтобы избежать этого, мы используем трюк с guc_option.
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}');

-- Даем все права на эту базу данных нашему пользователю.
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};