$stackContent = @"
version: '3.8'

services:
  # 1. BANCO DE DADOS COMPARTILHADO (Economia de RAM)
  postgres:
    image: pgvector/pgvector:pg15
    container_name: postgres_db_ia
    restart: always
    environment:
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=senha_segura_db
      - POSTGRES_DB=chatwoot 
    volumes:
      - postgres_data_ia:/var/lib/postgresql/data

  redis:
    image: redis:alpine
    container_name: redis_cache_ia
    restart: always
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data_ia:/data

  # 2. MOTOR DE IA E BANCO VETORIAL
  ollama:
    image: ollama/ollama:latest
    container_name: ollama_ia
    restart: unless-stopped
    volumes:
      - ollama_data_ia:/root/.ollama
    ports:
      - "11434:11434"

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant_vector_db_ia
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data_ia:/qdrant/storage

  # 3. AUTOMACAO (n8n)
  n8n:
    image: docker.n8n.io/n8nio/n8n
    container_name: n8n_ia
    restart: always
    environment:
      - N8N_HOST=n8n-ia.cristhiansancore.com.br 
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - NODE_ENV=production
      - WEBHOOK_URL=https://n8n-ia.cristhiansancore.com.br 
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=admin
      - DB_POSTGRESDB_PASSWORD=senha_segura_db
    ports:
      - "5678:5678"
    volumes:
      - n8n_data_ia:/home/node/.n8n
    depends_on:
      - postgres

  # 4. EVOLUTION API (WhatsApp)
  evolution-api:
    image: evoapicloud/evolution-api:latest
    container_name: evolution_api_ia
    restart: always
    environment:
      - SERVER_URL=https://api-ia.cristhiansancore.com.br 
      - SERVER_TYPE=http
      - CORS_ORIGIN=*
      - DEL_INSTANCE=false
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://admin:senha_segura_db@postgres:5432/evolution?schema=public
      - DATABASE_CONNECTION_CLIENT_NAME=evolution
      - REDIS_URI=redis://redis:6379
      - CACHE_REDIS_URI=redis://redis:6379/1
      - GLOBAL_APIKEY=Sancore@2404
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY=Sancore@2404
      - CHATWOOT_ENABLED=true
      - CHATWOOT_MESSAGE_READ=true
      - CHATWOOT_MESSAGE_DELETE=true
    ports:
      - "8080:8080"
    volumes:
      - evolution_instances_ia:/evolution/instances
    depends_on:
      - postgres
      - redis

  # 5. CHATWOOT (Atendimento Omnichannel)
  chatwoot_web:
    image: chatwoot/chatwoot:latest
    container_name: chatwoot_web_ia
    restart: always
    environment: &chatwoot_env
      - SECRET_KEY_BASE=substitua_por_uma_hash_segura_aqui
      - FRONTEND_URL=https://chat-ia.cristhiansancore.com.br 
      - DEFAULT_LOCALE=pt_BR
      - REDIS_URL=redis://redis:6379
      - POSTGRES_DATABASE=chatwoot
      - POSTGRES_HOST=postgres
      - POSTGRES_USERNAME=admin
      - POSTGRES_PASSWORD=senha_segura_db
    ports:
      - "3000:3000"
    depends_on:
      - postgres
      - redis

  chatwoot_init:
    image: chatwoot/chatwoot:latest
    container_name: chatwoot_init_ia
    restart: "no"
    command: bundle exec rake db:chatwoot_prepare
    environment: *chatwoot_env
    depends_on:
      - postgres
      - redis

  chatwoot_worker:
    image: chatwoot/chatwoot:latest
    container_name: chatwoot_worker_ia
    restart: always
    command: bundle exec sidekiq -C config/sidekiq.yml
    environment: *chatwoot_env
    depends_on:
      - postgres
      - redis

  # 6. CLOUDFLARE TUNNEL
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared_tunnel_ia
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token eyJhIjoiNTliMjg0ZjliMjEyNDJhMzc4ZjRjMWY4OGY1YTU1YWMiLCJ0IjoiZWRhNjMzYTktMGVmZS00MDQ2LTljNTktNDEyMGIxMTljMTMyIiwicyI6Ik5qY3hPRGM1WmpBdFpXRmpNUzAwWWpNekxXSmxOemd0TldNd056WmtNR1UxWm1KaiJ9

  # 7. PAINEL RAG - CAMARA DE VEREADORES
  painel-rag:
    image: ghcr.io/cristhian-sancore/painel-rag-camara:latest
    container_name: painel_rag_camara
    restart: always
    environment:
      - OLLAMA_URL=http://ollama:11434
      - QDRANT_URL=http://qdrant:6333
      - DATABASE_URL=postgresql+asyncpg://admin:senha_segura_db@postgres:5432/painel_rag
      - REDIS_URL=redis://redis:6379
      - SUPERADMIN_EMAIL=admin@camara.gov.br
      - SUPERADMIN_PASSWORD=Admin@2024
      - SUPERADMIN_NOME=Super Administrador
      - JWT_SECRET=troque-por-uma-chave-segura-de-64-caracteres
      - LLM_MODEL=llama3
      - EMBEDDING_MODEL=nomic-embed-text
      - QDRANT_COLLECTION=camara_documentos
      - MAX_UPLOAD_SIZE_MB=50
    ports:
      - "8501:8000"
    volumes:
      - painel_uploads:/app/uploads
    depends_on:
      - postgres
      - redis
      - ollama
      - qdrant
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  postgres_data_ia:
  redis_data_ia:
  ollama_data_ia:
  qdrant_data_ia:
  n8n_data_ia:
  evolution_instances_ia:
  painel_uploads:
"@

$body = @{
    stackFileContent = $stackContent
    prune = $true
    pullImage = $true
} | ConvertTo-Json -Depth 3

$headers = @{
    "X-API-Key" = "ptr_u1U9VC6iS9m0gLl2DJ4jMWvOCqt2KYNNaQ0NNs/+OFk="
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Method Put -Uri "https://portainer.cristhiansancore.com.br/api/stacks/5?endpointId=3" -Headers $headers -Body $body -TimeoutSec 180
    Write-Output "SUCESSO! Stack atualizada."
    Write-Output "Status: $($response.Status) | Name: $($response.Name) | Id: $($response.Id)"
} catch {
    $errorBody = $_.ErrorDetails.Message
    Write-Output "ERRO: $errorBody"
    Write-Output "Exception: $($_.Exception.Message)"
}
