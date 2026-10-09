# Request (synthetic)

From product: "fullname" is confusing in the API and admin UI. Please:

1. Rename `users.fullname` to `display_name` everywhere.
2. Add a required `region` field to every user (values: `emea`, `amer`, `apac`).
   New sign-ups will pick a region. We are not sure yet what existing users should get.

We would like this in the next release if possible.
