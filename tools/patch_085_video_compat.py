from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

s = s.replace(
    'import androidx.media3.common.MediaItem\nimport androidx.media3.common.Player\nimport androidx.media3.exoplayer.ExoPlayer',
    'import androidx.media3.common.MediaItem\nimport androidx.media3.common.Player\nimport androidx.media3.common.PlaybackException\nimport androidx.media3.exoplayer.DefaultLoadControl\nimport androidx.media3.exoplayer.DefaultRenderersFactory\nimport androidx.media3.exoplayer.ExoPlayer'
)

s = s.replace(
    '    private var watermarkEnabled = false',
    '    private var watermarkEnabled = false\n    private var lastPlaybackError = ""'
)

old_builder = '''        player = ExoPlayer.Builder(this).build()\n        playerView.player = player\n        player.repeatMode = Player.REPEAT_MODE_OFF\n        player.addListener(object : Player.Listener {\n            override fun onPlaybackStateChanged(playbackState: Int) {\n                if (playbackState == Player.STATE_ENDED && activeItems.isNotEmpty()) syncPlayback(true)\n            }\n        })'''

new_builder = '''        val renderersFactory = DefaultRenderersFactory(this)\n            .setEnableDecoderFallback(true)\n        val loadControl = DefaultLoadControl.Builder()\n            .setBufferDurationsMs(15000, 60000, 1500, 3000)\n            .setPrioritizeTimeOverSizeThresholds(true)\n            .build()\n        player = ExoPlayer.Builder(this, renderersFactory)\n            .setLoadControl(loadControl)\n            .build()\n        playerView.player = player\n        player.repeatMode = Player.REPEAT_MODE_OFF\n        player.addListener(object : Player.Listener {\n            override fun onPlaybackStateChanged(playbackState: Int) {\n                if (playbackState == Player.STATE_READY) lastPlaybackError = ""\n                if (playbackState == Player.STATE_ENDED && activeItems.isNotEmpty()) syncPlayback(true)\n            }\n\n            override fun onPlayerError(error: PlaybackException) {\n                val mediaName = activeItems.getOrNull(currentIndex)?.name ?: "vídeo"\n                val detail = error.cause?.message ?: error.message ?: "erro de reprodução"\n                lastPlaybackError = "Falha em $mediaName: $detail".take(240)\n            }\n        })'''

if old_builder not in s:
    raise SystemExit('Bloco de criação do player não encontrado')
s = s.replace(old_builder, new_builder)

needle = '''            .put("currentPlaylistId", currentPlaylistId)\n            .toString()'''
replacement = '''            .put("currentPlaylistId", currentPlaylistId)\n            .put("playbackError", lastPlaybackError)\n            .toString()'''
if needle not in s:
    raise SystemExit('Heartbeat não encontrado para playbackError')
s = s.replace(needle, replacement)

p.write_text(s, encoding='utf-8')
print('Compatibilidade de vídeo 0.8.5 aplicada sem alterar conexão/sincronização')
