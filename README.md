# SPP Gas Readings for Home Assistant

HACS-kompatibilná vlastná integrácia pre Home Assistant, ktorá načítava
odpočty plynomera zo služby SPP - distribúcia.

Integrácia vytvorí pre vybrané odberné miesto senzor s posledným celkovým
stavom plynomera v metroch kubických. Senzor používa
`state_class: total_increasing`, takže je vhodný pre dashboardy, dlhodobé
štatistiky a Energy dashboard Home Assistantu.

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

Hodinové načítanie neznamená, že SPP vytvorí nový odpočet každú hodinu. Stav
senzora sa zmení až vtedy, keď API SPP sprístupní novší odpočet.

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
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
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

Senzor používa kombináciu `device_class: gas`, jednotku `m³` a
`state_class: total_increasing`, preto ho možno pridať v:

```text
Nastavenia -> Dashboardy -> Energia -> Plyn
```

Po prvom vytvorení sa senzor nemusí v ponuke objaviť okamžite. Home Assistant
najprv potrebuje vytvoriť dlhodobé štatistiky, čo môže trvať približne hodinu.

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

Jednotkové testy autentifikácie a obnovy tokenu možno spustiť príkazom:

```bash
python3 -m unittest discover -s tests -v
```
