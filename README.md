# SPP Gas Readings for Home Assistant

HACS-kompatibilná vlastná integrácia pre Home Assistant, ktorá načítava
odpočty plynomera zo služby SPP - distribúcia.

Integrácia vytvorí pre vybrané odberné miesto senzor s posledným celkovým
stavom plynomera v metroch kubických. Senzor používa
`state_class: total_increasing`, takže je vhodný pre dashboardy, dlhodobé
štatistiky a Energy dashboard Home Assistantu. Od verzie `0.2.0` sa zároveň
spätne importujú všetky odpočty dostupné v SPP.

## Ako integrácia funguje

1. Používateľ zadá e-mail a heslo používané v aplikácii SPP - distribúcia.
2. Integrácia sa prihlási do identity služby SPP cez OAuth password grant.
3. Krátkodobý OAuth token vymení cez `POST /api/v1/login-web` za token
   mobilného API.
4. Cez `GET /api/v1/point` načíta dostupné odberné miesta.
5. Ak účet obsahuje viac odberných miest, používateľ si jedno vyberie.
6. Každú hodinu integrácia načíta históriu odpočtov vybraného odberného
   miesta od `2017-01-01` po aktuálny dátum.
7. Odpočty zoradí podľa dátumu a stav senzora nastaví na hodnotu `value`
   z najnovšieho záznamu.
8. Všetky platné odpočty zapíše podľa ich dátumu do externej dlhodobej
   štatistiky Home Assistantu.

Ak API token prestane platiť, klient sa automaticky prihlási znova a požiadavku
zopakuje. Prihlasovacie údaje sú uložené v config entry Home Assistantu a
odosielajú sa iba službám SPP. Neukladajú sa do zdrojového kódu ani do Git
repozitára.

Jedna config entry reprezentuje jedno odberné miesto. Ďalšie odberné miesto
možno pridať opätovným spustením konfigurácie integrácie.

## Vytvorený senzor

Integrácia vytvorí senzor `Gas meter reading` s týmito vlastnosťami:

- jednotka: `m³`
- `device_class: gas`
- `state_class: total_increasing`
- stav: posledný celkový stav plynomera
- `reading_date`: dátum použitého odpočtu
- `meter`: číslo plynomera
- `last_period_consumption_m3`: spotreba uvedená pri poslednom odpočte
- `historical_statistics_id`: ID importovanej dlhodobej štatistiky
- `imported_readings`: počet odpočtov zaradených do importu
- `sampled_historical_statistics_id`: ID denne rozpočítanej štatistiky
- `imported_sampled_readings`: počet importovaných denných bodov

Hodinové načítanie neznamená, že SPP vytvorí nový odpočet každú hodinu. Stav
senzora sa zmení až vtedy, keď API SPP sprístupní novší odpočet.

## Import historických odpočtov

Pre každé odberné miesto vznikne externá dlhodobá štatistika s ID v tvare:

```text
spp_gas:<point_id>_gas_consumption
```

Každý odpočet sa uloží na polnoc jeho dátumu v časovej zóne
`Europe/Bratislava`. Hodnota `state` obsahuje skutočný stav plynomera a `sum`
obsahuje kumulatívnu spotrebu od prvého dostupného odpočtu. Prvý odpočet tvorí
nulový základ. Pri ďalších sa použije spotreba `consumption` vrátená SPP; ak
chýba, integrácia použije rozdiel stavov rovnakého plynomera.

Celá dostupná história sa kontroluje každú hodinu. Opakovaný import rovnakého
dátumu aktualizuje existujúci štatistický bod, takže nevytvára duplikáty a vie
zohľadniť aj neskoršiu opravu odpočtu zo strany SPP.

Zároveň vznikne druhá štatistika s rovnomerne rozpočítanou dennou spotrebou:

```text
spp_gas:<point_id>_gas_consumption_vzorkovana
```

Spotreba medzi dvoma odpočtami sa vydelí počtom kalendárnych dní. Napríklad
prírastok 30 m³ medzi 1. a 4. januárom vytvorí spotrebu 10 m³ pre 2., 3. a
4. január. Štatistika má bod na miestnej polnoci každého dňa a jej `state` aj
`sum` obsahujú kumulatívnu rozpočítanú spotrebu. Po poslednom známom odpočte
integrácia ďalšiu spotrebu neodhaduje.

## Inštalácia cez HACS

Repozitár musí byť dostupný cez GitHub alebo inú URL podporovanú HACS.

1. V HACS otvorte menu `Custom repositories`.
2. Pridajte URL repozitára a ako typ vyberte `Integration`.
3. Vyhľadajte a nainštalujte `SPP Gas Readings`.
4. Reštartujte Home Assistant.
5. Otvorte `Nastavenia -> Zariadenia a služby` a pridajte integráciu
   `SPP Gas Readings`.

## Manuálna inštalácia

Na lokálne testovanie skopírujte celý adresár
`custom_components/spp_gas` do konfiguračného adresára Home Assistantu:

```text
/config/custom_components/spp_gas/
```

Výsledná štruktúra má vyzerať takto:

```text
/config/
└── custom_components/
    └── spp_gas/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── history.py
        ├── manifest.json
        ├── models.py
        ├── sensor.py
        ├── strings.json
        ├── certs/
        │   └── spp_login_ca_bundle.pem
        └── translations/
            ├── en.json
            └── sk.json
```

Po skopírovaní reštartujte Home Assistant.

## Nastavenie integrácie

1. Otvorte `Nastavenia -> Zariadenia a služby`.
2. Kliknite na `Pridať integráciu`.
3. Vyhľadajte `SPP Gas Readings`.
4. Zadajte e-mail a heslo používané v SPP - distribúcia.
5. Ak sa zobrazí výber, zvoľte požadované odberné miesto.
6. Otvorte vytvorené zariadenie a skontrolujte senzor
   `Gas meter reading`.

Home Assistant vytvorí ID entity podľa názvu zariadenia. Môže vyzerať
napríklad takto:

```text
sensor.dom_gas_meter_reading
```

Skutočné ID skontrolujte priamo v detaile entity.

## Bežný dashboard

Senzor možno pridať cez editor dashboardu alebo pomocou YAML karty:

```yaml
type: entity
entity: sensor.dom_gas_meter_reading
name: Stav plynomera
```

Ukážkové ID nahraďte skutočným ID entity z Home Assistantu.

## Energy dashboard

V nastavení plynu vyberte denne rozpočítanú štatistiku pomenovanú podľa
odberného miesta, napríklad
`<názov odberného miesta> gas consumption (daily average)`:

```text
Nastavenia -> Dashboardy -> Energia -> Plyn
```

Import sa zaradí do fronty recorderu počas prvého načítania integrácie. Nová
štatistika sa preto nemusí v ponuke objaviť okamžite; zvyčajne stačí niekoľko
minút. Jej presné ID je dostupné v atribúte
`sampled_historical_statistics_id` entity `Gas meter reading` a v
`Vývojárske nástroje -> Štatistiky`. Pôvodná štatistika s bodmi iba v dňoch
skutočných odpočtov zostáva dostupná pod názvom
`<názov odberného miesta> gas consumption`.

## Diagnostika

Podrobnejšie logovanie možno zapnúť v `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.spp_gas: debug
```

Po reštarte sú záznamy dostupné v `Nastavenia -> Systém -> Protokoly`.

Najčastejšie chyby:

- `Prihlásenie zlyhalo` - skontrolujte e-mail a heslo.
- `Nepodarilo sa pripojiť k SPP API` - skontrolujte internetové pripojenie,
  DNS a dostupnosť služieb SPP.
- `Účet nemá dostupné odberné miesta` - prihlásenie prešlo, ale API nevrátilo
  žiadne odberné miesto.

## Používané API endpointy

- `POST https://login.spp-distribucia.sk/oxauth/restv1/token`
- `POST https://moapbe.spp-distribucia.sk/api/v1/login-web`
- `GET https://moapbe.spp-distribucia.sk/api/v1/point`
- `GET https://moapbe.spp-distribucia.sk/api/v1/point/{point_id}/deduction-history?meter=&filter[from]=2017-01-01&filter[to]=YYYY-MM-DD`

API nie je verejne dokumentované. Implementácia vychádza z komunikácie
oficiálnej mobilnej aplikácie zachytenej cez OWASP ZAP.

Prihlasovací server SPP momentálne neposiela správny intermediate TLS
certifikát. Integrácia preto obsahuje lokálny CA bundle s verejnými
certifikátmi `Thawte TLS RSA CA G1` a `DigiCert Global Root G2`. TLS overovanie
zostáva zapnuté vrátane kontroly hostname a platnosti certifikátov.

## Vývojové overenie

Jednotkové testy autentifikácie, obnovy tokenu a historického importu možno
spustiť príkazom:

```bash
python3 -m unittest discover -s tests -v
```
