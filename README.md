# Local cover art scripting (Picard 3 plugin)

Adds a **script** matching mode to MusicBrainz Picard's built-in *Local Files*
cover art provider. Instead of a regular expression, the mode evaluates a
tagger script for each file's metadata and uses the result as a file-name
pattern (supporting `*`, `?` and `{a,b}` wildcards) to find the matching local
cover art files.

Example pattern:

```
%albumartist% - %album%$if(%date%, [%date%],).{jpg,png}
```

This plugin registers its mode through Picard's `register_local_cover_art_mode`
extension point, so it requires no changes to Picard core. It requires a Picard
build that provides that extension point.

## Development

Run the end-to-end tests from a Picard source checkout so the plugin API is
importable:

```bash
PYTHONPATH=/path/to/picard:/path/to/picard-plugin-coverart-script \
    python -m pytest /path/to/picard-plugin-coverart-script/test
```

## License

GPL-2.0-or-later.
