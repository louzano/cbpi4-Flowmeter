# Sensor de fluxo e volume CBPI4

Este plugin foi portado da versão CBPI3 para o CBPI4 (https://github.com/nanab/Flowmeter)

O plugin inclui um sensor com ação para reiniciá-lo e uma etapa personalizada.
Use um resistor de 10k ohms no pino de sinal do sensor para proteger seu Raspberry Pi ou conecte o sensor de fluxo tipo Hall (YF-201 é recomendado) à sua placa de expansão Craftbeerpi nas portas do medidor de fluxo.

Conecte o sensor ao Raspberry Pi:
Vermelho -> 5V.
Preto -> GND.
Amarelo -> resistor de 10k ohms -> pino GPIO. (ou dados na placa de expansão. Nenhum resistor extra é necessário aqui)

- Instalação testada no CBPI 4 V4.7.1 - Codename: Winter Bock || GUIversion: 0.5.0 com SO Trixie
- Instalação: pipx runpip cbpi4 uninstall cbpi4-flowmeter

- Uso do sensor:
- Na página de configurações, escolha uma unidade para o volume (por exemplo, L, qt, gal, ...)
- Adicione o sensor em Hardware e escolha Fluxômetro como Tipo
- Vários parâmetros podem ser configurados:
- GPIO: define o GPIO usado para o sinal do sensor (conectado ao cabo amarelo)
- Display: define se o volume total ou a vazão por segundo será exibido
- Hertz: Aqui você precisa definir a frequência do seu sensor (Sinais por segundo). Isso deve estar documentado na folha de dados do sensor, como base use 7.5.

![Flowsensor Settings](https://github.com/avollkopf/cbpi4-Flowmeter/blob/main/SensorConfig.png?raw=true)

- Após a configuração, você precisa adicionar o sensor ao Painel.
- Selecione "Sim" para a ação, pois isso adicionará um menu adicional no lado direito do sensor para redefini-lo para 0.

![Flowsensor Action Setting](https://github.com/avollkopf/cbpi4-Flowmeter/blob/main/SensorActionSetting.png?raw=true)
![Flowsensor Action Button](https://github.com/avollkopf/cbpi4-Flowmeter/blob/main/SensorActionButton.png?raw=true)

    
- Ao pressionar o botão de menu no lado direito do sensor, um menu será exibido, onde você poderá redefinir o sensor.
- 
![Flowsensor Action Menu](https://github.com/avollkopf/cbpi4-Flowmeter/blob/main/SensorAction.png?raw=true)

Utilização do Flowstep: 
 - O plugin fornece uma etapa onde você pode definir um volume que deve fluir enquanto a etapa estiver ativa.
 - Você precisa selecionar seu sensor de fluxo como sensor.
 - Um atuador deve ser definido para acionar o início e a parada da etapa (por exemplo, uma válvula magnética).
 - Você precisa inserir o volume que deve fluir enquanto a etapa estiver ativo.
 - Quando a etapa começar, o sensor será definido como 0.
 - Você pode selecionar se o sensor deve ser definido como 0 após a conclusão da etapa.
   
![Flowstep](https://github.com/avollkopf/cbpi4-Flowmeter/blob/main/FlowStep.png?raw=true)

## Funcionalidades do sensor de fluxo

A funcionalidade *muito simples* do Sensor de Volume, adicionada recentemente, pode ser usada da seguinte forma: 
Parâmetros: 
 - GPIO: O número do pino GPIO na numeração BCM
 - impulsesPerVolumeUnit: a quantidade de impulsos que devem exibir o volume de 1 unidade. Isso é independente da unidade.
 - Basta usar a mesma unidade na etapa, se você a utiliza.
 - O Sensor de Volume apenas conta os impulsos e calcula o volume que o número de impulsos representa.
 
Ações: 
 - Reset Sensor: redefine a contagem de impulsos e o volume para 0
 - Fake Impulse: simula a detecção de um impulso (usado para teste se não tiver um sensor de fluxo)

## Changelog:

- 21.01.26: (0.0.7) Tradução PT-BR e ajuste para Trixie
- 10.06.23: (0.0.6) bump version to release
- 14.05.23: (0.0.6.rc1) added simple VolumeSensor and cbpi4 requirement
- 14.04.23: (0.0.5.a2) fixed bug in parameter generation
- 08.04.23: (0.0.5.a1) added test support for plugin settings selection branch
- 11.05.22: (0.0.4) Updated README (removed cbpi add)
- 10.05.22: (0.0.3) removed cbpi dependency
- 27.04.22: (0.0.2) Added MQTT based flowsensor with reset topic
- 02.10.21: (0.0.1) Initial Release

