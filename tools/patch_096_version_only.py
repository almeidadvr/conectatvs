from pathlib import Path

gradle = Path('app/build.gradle.kts')
g = gradle.read_text(encoding='utf-8')
# Esta versão NÃO altera rede. Apenas identifica o build kiosk sobre a base funcional 0.8.8.
g = g.replace('versionCode = 20', 'versionCode = 26')
g = g.replace('versionName = "0.9.0"', 'versionName = "0.9.6"')
gradle.write_text(g, encoding='utf-8')
print('Versão 0.9.6 aplicada sem alterar comunicação de rede.')
