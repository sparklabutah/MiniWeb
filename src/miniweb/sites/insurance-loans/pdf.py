"""Generate a downloadable PDF from the rendered benchmark policy document."""
import base64
from html import escape
from html.parser import HTMLParser
from io import BytesIO

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image


class _PolicyText(HTMLParser):
    def __init__(self):
        super().__init__(); self.inside=False; self.parts=[]; self.current=[]

    def flush(self):
        text=' '.join(''.join(self.current).split()); self.current=[]
        if text:self.parts.append(text)

    def handle_starttag(self,tag,attrs):
        if 'doc-wrapper' in dict(attrs).get('class','').split():self.inside=True
        if self.inside and tag in ('p','h1','h2','h3','tr','li'):self.flush()

    def handle_endtag(self,tag):
        if self.inside and tag in ('p','h1','h2','h3','tr','li','div'):self.flush()
        elif self.inside and tag in ('td','th'):self.current.append(' | ')

    def handle_data(self,data):
        if self.inside:self.current.append(data)


def policy_pdf(html,policy):
    parser=_PolicyText();parser.feed(html);parser.flush()
    output=BytesIO();styles=getSampleStyleSheet()
    story=[]
    for text in parser.parts:
        story.extend([Paragraph(escape(text),styles['BodyText']),Spacer(1,5)])
    if policy.get('signed'):
        story.append(Paragraph(escape('Signed by '+str(policy.get('signed_by',''))+' on '+str(policy.get('signed_date',''))+' ('+str(policy.get('signed_method',''))+')'),styles['Heading2']))
        drawing=policy.get('signature_drawing','')
        if drawing.startswith('data:image/png;base64,'):
            image=Image(BytesIO(base64.b64decode(drawing.split(',',1)[1])))
            ratio=min(360/image.imageWidth,100/image.imageHeight)
            image.drawWidth=image.imageWidth*ratio;image.drawHeight=image.imageHeight*ratio;story.append(image)
    SimpleDocTemplate(output,title='Policy '+policy['policy_number'],author='Cascadia Insurance & Lending').build(story)
    return output.getvalue()
