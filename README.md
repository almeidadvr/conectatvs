# Conecta Mídia 0.4.0

Player de mídia digital para Android, tablets, Android TV e Google TV, integrado ao painel Conecta Sign Desktop.

## O que esta versão inclui

- Nome exibido do aplicativo: Conecta Mídia.
- Ícone com a logo oficial enviada pelo usuário.
- Banner próprio para Android TV / Google TV.
- Compatibilidade com tablets Android.
- Android Gradle Plugin 8.7.3 + Gradle 8.9.
- Java/JVM 17.
- compileSdk/targetSdk 35 e minSdk 26.
- Launcher para Android TV / Google TV e Android convencional.
- Suporte ao controle remoto e toque.
- Código de pareamento de 6 dígitos.
- Descoberta do servidor nas portas 8787 a 8797.
- Vídeos com Media3/ExoPlayer.
- Imagens com duração configurada pela playlist.
- Cache local para continuar reproduzindo offline.
- Heartbeat e atualização periódica da playlist.
- Tentativa de abertura após BOOT_COMPLETED.

## Build automático

O workflow em `.github/workflows/build-apk.yml` gera o APK debug automaticamente.
