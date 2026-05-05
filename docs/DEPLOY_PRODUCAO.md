# Deploy em producao

Este checklist prepara a publicacao do Repositorio de Projetos CT/UFPB em um servidor Linux com Docker Compose, MySQL, Gunicorn e Nginx.

## 1. Pre-requisitos do servidor

- Linux com Docker e Docker Compose Plugin instalados.
- Porta HTTP interna liberada para a stack ou para o proxy reverso.
- Dominio definido, por exemplo `projetos.ct.ufpb.br`.
- Certificado HTTPS configurado no proxy externo, balanceador ou infraestrutura institucional.
- Rotina de backup autorizada para banco e volumes.

## 2. Preparar o ambiente

No servidor, copie o modelo de producao:

```bash
cp .env.production.example .env
```

Edite `.env` e substitua obrigatoriamente:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- variaveis SMTP (`DJANGO_EMAIL_HOST`, usuario, senha e remetente)

Mantenha:

```env
DJANGO_DEBUG=0
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SECURE_HSTS_SECONDS=31536000
```

Se o proxy externo ainda nao estiver com HTTPS pronto, nao habilite HSTS no dominio final antes de confirmar a cadeia HTTPS.

## 3. Validar configuracao

```bash
docker compose -f docker-compose.prod.yml config
```

Se o comando acima falhar, corrija a `.env` antes de subir containers.

Depois que os containers estiverem construidos ou em ambiente com dependencias instaladas, rode tambem:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py check_production_ready --strict
```

Esse comando verifica `DEBUG`, chave secreta, hosts, CSRF, banco, HTTPS, SMTP e caminhos de arquivos.

## 4. Subir a stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

A stack executa automaticamente:

- `migrate`
- `collectstatic`
- healthcheck da aplicacao em `/healthz/`
- healthcheck do Nginx em `/nginx-health`

## 5. Criar dados iniciais

Crie categorias, status, edificacoes iniciais e o primeiro administrador:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py seed_initial_data --create-admin --username admin --password "troque-esta-senha"
```

Depois do primeiro acesso, troque a senha e crie usuarios nominais.

## 6. Verificar saude

```bash
curl -i http://127.0.0.1/healthz/
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 web
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
```

O endpoint `/healthz/` deve retornar:

```json
{"status":"ok","database":"ok"}
```

## 7. Testar fluxos essenciais

- Abrir catalogo publico.
- Filtrar projetos por busca, tipo, status e edificacao.
- Entrar com usuario administrador.
- Criar usuario e confirmar envio de e-mail de ativacao.
- Recuperar senha por e-mail.
- Cadastrar projeto, imagens e arquivos.
- Conferir que visitante baixa arquivos apenas de projetos publicos finalizados.
- Conferir que usuarios autenticados acessam os arquivos permitidos.

## 8. Backup minimo

O backup deve incluir:

- dump do MySQL
- volume `media_data`
- volume `private_media_data`

Dump do banco:

```bash
docker compose -f docker-compose.prod.yml exec mysql mysqldump -u root -p repo_arquitetonico_prod > backup_repo_arquitetonico.sql
```

Arquivos dos volumes:

```bash
docker run --rm -v repositorio-projetos-arquitetonicos_media_data:/data -v "$PWD/backups:/backup" alpine tar czf /backup/media_data.tar.gz -C /data .
docker run --rm -v repositorio-projetos-arquitetonicos_private_media_data:/data -v "$PWD/backups:/backup" alpine tar czf /backup/private_media_data.tar.gz -C /data .
```

Confirme o nome real dos volumes com:

```bash
docker volume ls
```

## 9. Restauracao

Antes de considerar o ambiente em producao definitiva, faca pelo menos um teste de restauracao em homologacao:

```bash
docker compose -f docker-compose.prod.yml exec -T mysql mysql -u root -p repo_arquitetonico_prod < backup_repo_arquitetonico.sql
```

Restaure tambem os arquivos de `media_data` e `private_media_data` e valide o download de arquivos no sistema.

## 10. Operacao diaria

Comandos uteis:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml restart web
```

Para atualizar a aplicacao:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

O servico `app-init` roda migrations e coleta de arquivos estaticos antes do `web` ficar disponivel.
