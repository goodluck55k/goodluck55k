"""Generate a LOCAL-only README preview. This is not a hosted website."""
from html import escape
from common import ROOT, config, write_text
from render import readme


def main():
    c = config()
    markup = readme(c).replace('src="assets/', 'src="../assets/').replace('srcset="assets/', 'srcset="../assets/')
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(c['user'])} · Local README preview</title>
<style>
* {{ box-sizing: border-box; }}
html,body {{ margin:0; padding:0; background:{c['themes']['light']['bg']}; }}
main {{ width:100%; max-width:{c['layout']['desktop_width']}px; margin:0 auto; line-height:0; }}
picture, a {{ display:block; margin:0; padding:0; }}
p {{ margin:0; padding:0; }}
img {{ display:block; width:100%; max-width:100%; height:auto; }}
@media (prefers-color-scheme:dark) {{ html,body {{ background:{c['themes']['dark']['bg']}; }} }}
</style></head><body><main>{markup}</main></body></html>'''
    write_text(ROOT / "previews/index.html", page)
    print("Local preview: previews/index.html")


if __name__ == "__main__":
    main()
