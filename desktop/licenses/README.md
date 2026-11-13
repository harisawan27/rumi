# Bundled font and WebView2 SDK notices

These files preserve upstream license/notice text for redistributed assets:

- `Inter-OFL.txt`: <https://github.com/google/fonts/blob/main/ofl/inter/OFL.txt>
- `Cormorant-Garamond-OFL.txt`: <https://github.com/google/fonts/blob/main/ofl/cormorantgaramond/OFL.txt>
- `WebView2-LICENSE.txt` and `WebView2-NOTICE.txt`: the root notices from the
  official `Microsoft.Web.WebView2` NuGet package **1.0.3856.49**, matching the
  Core/WinForms DLLs bundled with pinned pywebview 6.2.1.
  <https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49>

`write_notices.py` includes these notices with installed Python and JavaScript
dependency notices in the portable package. Recheck SDK DLL versions and their
matching notices when upgrading pywebview. The installed Edge runtime itself is
not redistributed in this package.
