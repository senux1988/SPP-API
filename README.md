# SPP Gas Readings for Home Assistant

HACS-compatible custom integration for SPP - distribucia gas meter readings.

The integration creates one sensor per configured delivery point. The sensor state is the latest total gas meter reading in cubic meters and uses `state_class: total_increasing`, so it can be used in dashboards and long-term statistics.

## Install with HACS

1. Add this repository as a custom HACS integration repository.
2. Install `SPP Gas Readings`.
3. Restart Home Assistant.
4. Add the integration from Settings -> Devices & services.

## Notes

Authentication follows the mobile application flow captured from SPP: the integration
obtains an OAuth token from `login.spp-distribucia.sk` and exchanges it through
`POST /api/v1/login-web` for the mobile API token. Credentials stay in the Home
Assistant config entry and are sent only to SPP services.

Captured API endpoints used by the integration:

- `POST https://login.spp-distribucia.sk/oxauth/restv1/token`
- `POST https://moapbe.spp-distribucia.sk/api/v1/login-web`
- `GET https://moapbe.spp-distribucia.sk/api/v1/point`
- `GET https://moapbe.spp-distribucia.sk/api/v1/point/{point_id}/deduction-history?meter=&filter[from]=2017-01-01&filter[to]=YYYY-MM-DD`
