# Repositorio de Projetos CT/UFPB

Aplicativo Django para catalogo publico e repositorio autenticado de projetos da Assessoria de Projetos Urbanisticos e Infraestrutura do Centro de Tecnologia da UFPB.

## O que ja vem implementado

- Catalogo publico de projetos com busca e filtros.
- Login e senha com perfis `Admin`, `Equipe` e `Leitor`.
- Gestao de usuarios restrita a administradores.
- Cadastro de pessoas e equipe independente de usuarios.
- Projetos com descricao, imagem de capa, categorias multiplas, equipe e metadados.
- Arquivos privados versionados por projeto, com tipo, versao, responsavel, status e download autenticado.
- Dashboard interno de acompanhamento.
- Docker Compose para desenvolvimento e stack separada para producao em Linux com Nginx.

## Desenvolvimento no Windows

1. Copie o arquivo de ambiente:

```powershell
Copy-Item .env.example .env
```

2. Suba a aplicacao:

```powershell
docker compose up --build
```

3. Em outro terminal, crie categorias iniciais e um admin:

```powershell
docker compose exec web python manage.py seed_initial_data --create-admin --username admin --password "troque-esta-senha"
```

4. Acesse:

- Aplicacao: [http://localhost:8000](http://localhost:8000)
- Admin Django: [http://localhost:8000/admin/](http://localhost:8000/admin/)

### Verificacao rapida sem Docker

Para conferir alteracoes locais com SQLite:

```powershell
.\iniciar.bat
```

Para abrir o navegador automaticamente:

```powershell
.\iniciar.bat -AbrirNavegador
```

## Producao em Linux

1. Copie `.env.production.example` para `.env`.

2. Antes do primeiro deploy, ajuste obrigatoriamente:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT=1`
- `DJANGO_SECURE_HSTS_SECONDS=31536000`
- `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`
- `GUNICORN_WORKERS` e `GUNICORN_TIMEOUT`, se quiser tunar o Gunicorn

3. Suba a stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

4. Crie os dados iniciais:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py seed_initial_data --create-admin --username admin --password "troque-esta-senha"
```

Para o roteiro completo de publicacao, validacao, backup e operacao, consulte `docs/DEPLOY_PRODUCAO.md`.

### O que a stack de producao faz

- `app-init` executa `migrate` e `collectstatic` antes do Gunicorn subir.
- `web` espera o banco e a inicializacao ficarem saudaveis.
- `nginx` so sobe depois que o endpoint `/healthz/` estiver respondendo.
- o container Python roda como usuario nao-root.
- o Django falha cedo se segredos, hosts, origens CSRF ou credenciais MySQL inseguras forem mantidos em modo de producao.

### HTTPS e proxy externo

O `docker-compose.prod.yml` publica `80:80`. Em producao, o ideal e colocar essa stack atras de um proxy ou balanceador que termine HTTPS.

Se o proxy externo encaminhar `X-Forwarded-Proto: https`, o Nginx interno preserva esse valor para o Django. Isso e necessario para cookies seguros, redirecionamento HTTPS e CSRF funcionarem corretamente.

## Testes

Com Docker:

```bash
docker compose run --rm web python manage.py test
```

Para validar pendencias de configuracao antes da producao:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py check_production_ready --strict
```

Sem Docker, usando SQLite apenas para validacao local:

```powershell
$env:DJANGO_USE_SQLITE='1'
python manage.py test
```

## Backup

O backup minimo deve incluir:

- dump do banco MySQL
- volume `private_media_data`, com os arquivos tecnicos privados
- volume `media_data`, com imagens publicas e capas

Exemplo de dump:

```bash
docker compose -f docker-compose.prod.yml exec mysql mysqldump -u root -p repo_arquitetonico > backup_repo_arquitetonico.sql
```

## Observacoes

- Arquivos tecnicos nao sao servidos diretamente pelo Nginx; o download passa pela aplicacao Django. Visitantes podem baixar arquivos apenas de projetos publicos finalizados; usuarios autenticados seguem as permissoes internas.
- Imagens publicas de capa ficam em `MEDIA_ROOT` e podem ser servidas pelo Nginx.
- O endpoint de saude da aplicacao e `/healthz/`.
