# SPP Gas Readings for Home Assistant

HACS-compatible custom integration for SPP - distribucia gas meter readings.

The integration creates one sensor per configured delivery point. The sensor state is the latest total gas meter reading in cubic meters and uses `state_class: total_increasing`, so it can be used in dashboards and long-term statistics.

## Install with HACS

1. Add this repository as a custom HACS integration repository.
2. Install `SPP Gas Readings`.
3. Restart Home Assistant.
4. Add the integration from Settings -> Devices & services.

## Notes

The ZAP capture included authenticated API calls, but not the initial SPP login exchange. The API client keeps authentication isolated in `custom_components/spp_gas/api.py`; if SPP requires the full `account.spp-distribucia.sk` OIDC flow, only that file should need adjustment after testing with a real account.

Captured API endpoints used by the integration:

- `GET https://moapbe.spp-distribucia.sk/api/v1/point`
- `GET https://moapbe.spp-distribucia.sk/api/v1/point/{point_id}/deduction-history?meter=&filter[from]=2017-01-01&filter[to]=YYYY-MM-DD`

