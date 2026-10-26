"""Make faithful before/after sheets from real browser screenshots."""
from PIL import Image,ImageDraw,ImageFont
from common import ROOT,write_bytes,write_text,config
from process_assets import png_bytes


def main():
    font=ImageFont.truetype(str(ROOT/"assets/fonts/LibreBaskerville.ttf"),18)
    for theme in ("light","dark"):
        for width in (840,375):
            before=Image.open(ROOT/"previews/round1/previews"/f"{theme}-{width}.png").convert("RGB")
            after=Image.open(ROOT/"previews"/f"{theme}-{width}.png").convert("RGB")
            gap=24
            paper=Image.new("RGB",(width*2+gap,max(before.height,after.height)+48),"#eeeae3")
            draw=ImageDraw.Draw(paper)
            draw.text((12,12),f"Round 1 / {width}px",font=font,fill="#171614")
            draw.text((width+gap+12,12),f"Round 2 / {width}px",font=font,fill="#171614")
            paper.paste(before,(0,48))
            paper.paste(after,(width+gap,48))
            write_bytes(ROOT/"previews"/f"comparison-{theme}-{width}.png",png_bytes(paper))
    for theme in ("light","dark"):
        panels=[Image.open(ROOT/"previews"/f"dyna-{factor}-{theme}.png").resize((840,Image.open(ROOT/"previews"/f"dyna-{factor}-{theme}.png").height//2),Image.Resampling.LANCZOS) for factor in (115,120,125)]
        height=sum(p.height+40 for p in panels)
        sheet=Image.new("RGB",(840,height),"#eeeae3")
        draw=ImageDraw.Draw(sheet)
        y=0
        for factor,panel in zip((115,120,125),panels):
            draw.text((20,y+9),f"Dyna +{factor-100}%"+(" / selected" if factor==120 else ""),font=font,fill="#171614")
            sheet.paste(panel,(0,y+40))
            y+=panel.height+40
        write_bytes(ROOT/"previews"/f"dyna-variants-{theme}.png",png_bytes(sheet))
    page='<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Round 1 / Round 2</title><style>body{max-width:1200px;margin:32px auto;padding:0 16px;background:#f6f5f2;color:#171614;font-family:serif}img{display:block;width:100%;height:auto;margin:20px 0 48px}a{color:inherit}</style><h1>第一轮 / 第二轮视觉对比</h1><p><a href="index.html">查看当前完整预览</a> · 左侧旧版，右侧新版；均为真实浏览器截图。</p>'
    for theme in ("light","dark"):
        for width in (840,375):
            page+=f'<h2>{theme} · {width}px</h2><img src="comparison-{theme}-{width}.png" alt="{theme} {width}px 原版与新版对照">'
    page+='<h2>戴拿比例：15% / 20% / 25%</h2><img src="dyna-variants-light.png" alt="戴拿三种比例，选用放大20%">'
    write_text(ROOT/"previews/comparison.html",page+'</html>')
    print("Four before/after sheets and Dyna 15/20/25% comparisons generated.")


if __name__=="__main__":
    main()
