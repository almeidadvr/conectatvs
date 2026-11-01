# Conecta Mídia - Marco da Etapa 1

Data do marco: 2026-11-01

Esta versão marca o encerramento da etapa atual de desenvolvimento do Conecta Mídia.

## Versões congeladas

- Console Windows: 0.9.2.14-TV-IDENTITY
- Player Android: 0.10.13
- Porta padrão: 8799
- API principal do Player: `/api/state` e `/api/tvs`

## Recursos consolidados

- Cadastro de TVs com código de pareamento.
- Grupos de TVs.
- Playlists e atribuição por TV/grupo.
- Agendamentos e recorrência.
- Reprodução local com cache offline.
- Auto-start do Player após reinicialização do Android/TV Box.
- Telemetria de rede, dispositivo e reprodução.
- Sincronização automática aproximada entre TVs do mesmo grupo e mesma playlist.
- Diagnóstico de sincronização no heartbeat.
- Limpeza segura de cache: mídia órfã só é apagada após 7 dias contínuos sem referência; playlists ativas/agendadas/recorrentes/fallback continuam protegidas.
- Dashboard, grupos, playlists, programações e detalhes de TVs no Console.
- Controle de acesso/licenciamento presentes no Console.

## Build reproduzível do Player

O Player 0.10.13 é produzido pela cadeia de patches versionados nesta branch e pelo workflow `.github/workflows/build-apk-01013.yml`.

Commit imediatamente anterior ao marco funcional do Player 0.10.13: `9e07b0b2d4b6e1bd606ef134e3594ceb5164488c`.

## Observação sobre o Console

O instalador 0.9.2.14 foi preservado como binário funcional desta etapa. O backend atual é um executável Go monolítico com interface embutida. O código-fonte completo e exato desse backend não está integralmente preservado nesta branch; por isso o pacote de encerramento deve manter o instalador, a interface extraída e o material-fonte histórico separados e claramente identificados.

## Próxima etapa

Qualquer desenvolvimento posterior deve partir deste marco e registrar uma nova versão, sem sobrescrever os instaladores e o snapshot desta etapa.
