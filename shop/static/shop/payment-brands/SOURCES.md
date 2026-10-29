# Official artwork provenance

Downloaded from official provider properties on 2026-10-30. These are provider
trademarks, not GadgetFlow artwork. No AI-generated or redrawn brand marks are used.

- `bkash.png`: `https://client.sandbox.bka.sh/bKash-logo.png`, referenced directly
  by the official bKash sandbox checkout page at `https://client.sandbox.bka.sh/`.
  Original magenta/black Bengali mark, unchanged.
- `mastercard.png`: `https://developer.mastercard.com/mastercard_icon_114x114.png`,
  linked by the official Mastercard developer portal. Original colored symbol,
  unchanged.
- `visa.svg`: the `svg[v-logo-visa]` brand mark rendered on
  `https://developer.visa.com/`. Original path/viewBox preserved; its rendered
  official Visa Blue `rgb(20, 52, 203)` was recorded as the standalone SVG fill,
  with an XML namespace so it renders independently of the portal's CSS.

The customer UI uses `object-fit: contain`, fixed bounding boxes and no filters,
recoloring, cropping or distorted proportions. Card marks appear only for the
explicit configured merchant brand list, with ready credentials/channel flags.
An empty or invalid list disables Card and shows no card acceptance marks.

Brand guidance reviewed:

- https://corporate.visa.com/en/about-visa/brand.html
- https://www.mastercard.com/brandcenter/us/en/brand-requirements/mastercard.html
- https://www.bkash.com/en/business/online-business

Confirm merchant acceptance and applicable brand-use approval with the provider
before enabling a brand. Do not use these assets to imply universal acceptance.
