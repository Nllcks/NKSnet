# Speedtest - App Desktop

## Sobre

Aplicativo Windows desktop para teste de velocidade de internet.
Tema escuro, interface moderna com botao circular dourado.

## Instalar dependencias

```powershell
pip install -r requirements.txt
```

## Executar

```powershell
python run.py
```

## Empacotar como .exe

```powershell
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SpeedTest --hidden-import speedtest run.py
```

O executavel sera gerado em `dist/SpeedTest.exe`.

O executavel sera gerado em `dist/SpeedTest.exe`.

## Estrutura do projeto

- `speedtest.py` - Ponto de entrada do aplicativo
- `app.py` - Interface grafica (MainWindow + CircularButton + dialogs)
- `worker.py` - Worker em thread separada para teste de velocidade
- `utils.py` - Deteccao de ISP, historico, configuracoes
- `requirements.txt` - Dependencias do projeto

## Funcionalidades

- Teste de Download, Upload, Ping e Jitter
- Botao circular dourado com animacao de progresso
- Deteccao automatica de ISP e localizacao via IP
- Historico local dos ultimos 50 testes
- Configuracao para inicio automatico
- Interface em portugues brasileiro
