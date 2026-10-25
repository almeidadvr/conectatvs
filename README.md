# Conecta Sign Player TV 0.3.1

Player de digital signage para Android TV / Google TV, integrado ao Conecta Sign Desktop.

## O que esta versão inclui

- Projeto Android pronto para abrir no Android Studio.
- Android Gradle Plugin 8.7.3 + Gradle 8.9.
- Java/JVM 17.
- compileSdk/targetSdk 35 e minSdk 26.
- Launcher para Android TV / Google TV.
- Ícone e banner próprios do Conecta Sign.
- Suporte ao controle remoto.
- Código de pareamento de 6 dígitos.
- Descoberta do servidor nas portas 8787 a 8797.
- Vídeos com Media3/ExoPlayer.
- Imagens com duração configurada pela playlist.
- Cache local para continuar reproduzindo offline.
- Heartbeat e atualização periódica da playlist.
- Tentativa de abertura após BOOT_COMPLETED.

## Build automático

Este repositório contém um workflow do GitHub Actions em `.github/workflows/build-apk.yml` para gerar o APK debug automaticamente.
