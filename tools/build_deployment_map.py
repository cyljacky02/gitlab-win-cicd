"""One-time seed for the editable Windows deployment map (not a deck build step).

Run explicitly: .venv-slides/Scripts/python tools/build_deployment_map.py
Native draw.io edits are authoritative afterwards: rerunning overwrites the full
map and both split views (nine files). Both exporters consume the same scene; PDF stays vector, PNG is rendered
from that PDF. Requires Microsoft JhengHei, reportlab and PyMuPDF.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
import math
import xml.etree.ElementTree as ET

import pymupdf as fitz
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/presentations/diagrams'
W, H = 2800, 1575
INK, MUTED = '#17324D', '#53677C'
BLUE, TEAL, AMBER, RED = '#2465A6', '#087F83', '#A36716', '#B34444'
FONT = 'JhengHei'


@dataclass
class Node:
    id: str
    x: float
    y: float
    w: float
    h: float
    text: str = ''
    fill: str = '#FFFFFF'
    stroke: str = '#CBD7E3'
    color: str = INK
    size: int = 28
    bold: bool = False
    parent: str = '1'
    kind: str = 'box'
    align: str = 'center'


@dataclass
class Edge:
    id: str
    source: str
    target: str
    points: list
    kind: str = 'control'
    color: str = BLUE


@dataclass
class Scene:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    width: int = W
    height: int = H

    def node(self, id, x, y, w, h, text='', **kw):
        self.nodes.append(Node(id, x, y, w, h, text, **kw))
        return id

    def text(self, id, x, y, w, h, text, **kw):
        return self.node(id, x, y, w, h, text, kind='text', **kw)

    def edge(self, id, source, target, points, **kw):
        self.edges.append(Edge(id, source, target, points, **kw))


def make_scene():
    s = Scene()
    s.text('title', 50, 25, 2700, 65, 'Windows 正式部署｜端到端目標架構與單機換版', size=46, bold=True, align='left')
    s.text('subtitle', 50, 94, 2700, 38, 'Production 範圍 • GitLab CE → Azure DevOps Server → Windows Targets • 目標設計／待 POC 驗證', size=28, color=MUTED, align='left')
    for id,x,w,fill,title in [
        ('dev',50,570,'#F0F5FB','開發／CI 區'),
        ('ops',650,1260,'#F1F5FA','授權部門管理區'),
        ('prod',1940,810,'#EDF7F5','Production｜授權存取')]:
        s.node(id,x,155,w,675,fill=fill,kind='container')
        s.text(id+'title',x+25,170,w-50,50,title,size=36,bold=True,parent=id,align='left')
    s.node('developer',100,235,470,75,'開發人員',fill='#FFF3DC',stroke='#D5AF6B',bold=True,parent='dev')
    s.node('gitlab',100,365,470,80,'GitLab CE｜程式碼／CI 編排',bold=True,parent='dev')
    s.node('runner',100,505,470,80,'GitLab Runner｜建置／測試',parent='dev')
    s.node('gitartifact',100,665,470,90,'GitLab Job Artifacts\n確切 project / pipeline / job',parent='dev')
    s.edge('push','developer','gitlab',[(335,310),(335,365)],kind='data')
    s.text('pushlabel',345,320,200,36,'① push',size=26,align='left')
    s.edge('ci','gitlab','runner',[(335,445),(335,505)])
    s.text('cilabel',345,456,200,36,'② CI 派工',size=26,align='left')
    s.edge('upload','runner','gitartifact',[(335,585),(335,665)],kind='data')
    s.text('uploadlabel',345,615,200,36,'上傳產物',size=26,align='left')

    s.node('receiver',700,365,360,105,'受保護自訂接收器\n認證／去重／耐久入列\nGitLab API 複核',size=27,parent='ops')
    s.node('queue',1130,365,350,105,'ADO Server\nQueue Build API\n固定 importer',size=27,parent='ops')
    s.node('deployer',1450,235,420,75,'授權 Deployer｜選版＋目標',fill='#FFF3DC',stroke='#D5AF6B',parent='ops',bold=True)
    s.node('release',1550,365,320,140,'Classic Release\nManual only＋事前核准\n關閉產物自動觸發',size=26,parent='ops',bold=True)
    s.node('importer',700,665,430,110,'管理 Build Agent｜Importer\n下載確切 job artifact\n驗 ZIP／hash／來源 manifest',size=26,parent='ops')
    s.node('store',1230,665,640,110,'ADO Server Build Artifacts\n固定 build 版本 • 不取 latest\n來源 SHA／job／hash 可追溯',size=28,parent='ops')
    s.edge('webhook','gitlab','receiver',[(570,390),(700,390)])
    s.text('webhooklabel',570,275,820,65,'③ Pipeline success webhook\n成功通知 ≠ Production 放行',size=26,color=BLUE)
    s.edge('enqueue','receiver','queue',[(1060,420),(1130,420)])
    s.text('queuelabel',1040,478,255,38,'④ 排入 importer',size=26,color=BLUE)
    s.edge('assign','queue','importer',[(1305,470),(1305,550),(915,550),(915,665)])
    s.text('assignlabel',1040,557,430,40,'派工（Agent 主動取工作）',size=26,color=BLUE)
    s.edge('request','importer','gitartifact',[(720,775),(720,820),(85,820),(85,710),(100,710)])
    s.text('requestlabel',100,775,470,35,'⑤ API 請求確切 job',size=26,color=BLUE)
    s.edge('artifact','gitartifact','importer',[(570,735),(700,735)],kind='data')
    s.text('artifactlabel',700,780,430,36,'⑤ 確切 artifact 內容返回',size=26,color=BLUE)
    s.edge('publish','importer','store',[(1130,720),(1230,720)],kind='data')
    s.text('publishlabel',1120,620,750,36,'⑥ 發布固定 build 產物',size=26,color=BLUE)
    s.edge('approve','deployer','release',[(1710,310),(1710,365)],color=AMBER)
    s.text('approvelabel',1450,315,240,40,'⑦ 手動放行',size=26,color=AMBER)
    s.edge('selectversion','store','release',[(1760,665),(1760,505)],color=AMBER)
    s.text('selectlabel',1480,550,260,70,'綁定不可變版本\n與核准目標',size=26,color=AMBER)
    s.node('f5',2300,245,390,85,'F5 LB｜應用流量',fill='#D9EEEA',stroke=TEAL,bold=True,parent='prod')
    s.text('f5note',1970,338,750,38,'維護控制身分／位置待確認；不預設 Agent 持憑證',size=26,color=TEAL,parent='prod')
    s.node('targets',1990,390,710,370,fill='#FFFFFF',stroke='#A8CAC4',kind='container',parent='prod')
    s.node('ingress',2020,405,650,65,'Deployment Group｜核准工作／指定產物',size=27,fill='#E5F2F0',stroke=TEAL,parent='targets',bold=True)
    for i,x,title in [('01',2020,'Windows 01'),('02',2240,'Windows 02'),('N',2460,'… Windows N')]:
        s.node('win'+i,x,520,210,195,fill='#F6FAFA',stroke='#B6D0CC',kind='container',parent='targets')
        s.text('wintitle'+i,x,525,210,40,title,size=27,bold=True,parent='win'+i)
        s.node('agent'+i,x+10,570,190,52,'部署 Agent',size=26,stroke=TEAL,parent='win'+i)
        s.node('app'+i,x+10,650,190,52,'應用服務',size=26,fill='#E5F2F0',stroke=TEAL,parent='win'+i)
        s.edge('job'+i,'ingress','agent'+i,[(x+5,470),(x+5,596),(x+10,596)])
        s.edge('local'+i,'agent'+i,'app'+i,[(x+105,622),(x+105,650)])
        s.edge('traffic'+i,'f5','app'+i,[(2690,285),(2730,285),(2730,785),(x+105,785),(x+105,702)],kind='traffic',color=TEAL)
    s.edge('releasework','release','ingress',[(1870,415),(2020,415)])
    s.text('worklabel',1880,225,400,70,'⑧ 已核准工作\n各 Agent 本機換版',size=26,color=BLUE)
    s.edge('download','store','ingress',[(1870,720),(1945,720),(1945,455),(2020,455)],kind='data')
    s.text('downloadlabel',1970,795,755,33,'N 可為數十台；群組線不表示同時部署或主機間派送',size=26,color=MUTED)
    s.text('architectureguard',50,842,2700,38,'存取界線｜CI、接收器、管理 Agent 無 Production 存取；放行前不得預拷（含工作目錄）。Agent 主動連 ADO；箭頭為工作／資料語意，非入站連線。',size=26,color=MUTED,align='left')

    s.text('lifetitle',50,901,1600,55,'⑧ 每一核准 Target｜健康且流量恢復，才可結案',size=36,bold=True,align='left')
    s.text('sequence',1700,912,1050,40,'建議逐台；失敗停止後續 • 批次／最低容量待定',size=27,color=MUTED,align='right')
    # Lifecycle nodes: explicit substeps retain stop -> backup -> deploy -> restart.
    s.node('fetch',50,1000,300,110,'1 下載＋驗證\n已放行版本\n部署鎖／前置檢查',size=27)
    s.node('isolate',420,1000,330,110,'2 down F5\n退出 LB 流量\n確認隔離／連線條件',size=27,fill='#FFF5E3',stroke=AMBER)
    s.node('backup',820,1000,300,110,'3 停止服務\n↓\n4 備份目前版本',size=27)
    s.node('deploy',1190,1000,300,110,'5 執行換版\n↓\n6 重啟服務',size=27)
    s.node('health',1560,1000,220,110,'7 健康\n檢查？',size=28,kind='diamond',fill='#EBF3FD',stroke=BLUE)
    s.node('restore',1900,1000,330,110,'8 up F5\n恢復 LB 流量\n驗證恢復成功',size=27,fill='#E5F2F0',stroke=TEAL)
    s.node('complete',2350,1000,380,110,'新版本部署完成\n留存人員／版本／目標／結果',size=26,fill='#D9EEEA',stroke=TEAL,bold=True)
    order=['fetch','isolate','backup','deploy','health','restore','complete']
    index={n.id:n for n in s.nodes}
    for a,b in zip(order,order[1:]):
        na,nb=index[a],index[b]
        s.edge('life'+a,a,b,[(na.x+na.w,1055),(nb.x,1055)],color=TEAL)
    s.text('healthy',1782,1010,115,36,'健康',size=26,color=TEAL)
    s.text('verified',2230,1010,120,36,'已驗證',size=26,color=TEAL)
    s.node('rollback',1190,1220,330,110,'保持隔離／停止失敗服務\n回復有效備份\n重啟服務',size=26,fill='#FFF1EC',stroke=RED)
    s.node('recoveryhealth',1580,1220,220,110,'復原健康\n檢查？',size=27,kind='diamond',fill='#FFF1EC',stroke=RED)
    s.node('recoverrestore',1900,1220,330,110,'up F5｜恢復 LB 流量\n驗證恢復成功',size=27,fill='#FFF5E3',stroke=AMBER)
    s.node('recovered',2350,1220,380,110,'部署失敗／復原成功\n非新版本部署完成',size=28,fill='#FFF5E3',stroke=AMBER,bold=True)
    s.edge('deployfail','deploy','rollback',[(1240,1110),(1240,1185),(1280,1185),(1280,1220)],color=RED)
    s.edge('healthfail','health','rollback',[(1670,1110),(1670,1165),(1400,1165),(1400,1220)],color=RED)
    s.text('failurelabel',1280,1120,490,36,'換版／啟動／檢查失敗',size=26,color=RED)
    for id,a,b,p in [('rcheck','rollback','recoveryhealth',[(1520,1275),(1580,1275)]),('rok','recoveryhealth','recoverrestore',[(1800,1275),(1900,1275)]),('rdone','recoverrestore','recovered',[(2230,1275),(2350,1275)])]:
        s.edge(id,a,b,p,color=AMBER)
    s.text('rhealthy',1805,1222,95,36,'健康',size=26,color=AMBER)
    s.text('rverified',2230,1222,120,36,'已驗證',size=26,color=AMBER)
    s.node('abort',50,1170,1070,135,'前置閘門失敗即中止、告警，不繼續換版\n取檔／驗證失敗：不進入隔離；隔離失敗：不得停服務\n停服務／備份失敗：不覆寫、保持隔離；確認健康才可回池',size=26,fill='#FFF5E3',stroke=AMBER,align='left')
    s.node('halt',50,1340,1070,65,'復原不健康／失敗／無有效備份 → 保持隔離、告警、人工處理',size=26,fill='#FCEDEC',stroke=RED)
    s.edge('rbfail','rollback','halt',[(1355,1330),(1355,1372),(1120,1372)],color=RED)
    s.edge('unhealthy','recoveryhealth','halt',[(1690,1330),(1690,1372),(1120,1372)],color=RED)
    s.text('unhealthylabel',1420,1378,440,35,'不健康 → 停止後續目標',size=26,color=RED)
    s.text('restoreguard',1890,1352,850,65,'任一 up F5 操作／驗證失敗：不得結案\n停止後續、告警並核對實際流量狀態',size=26,color=RED)
    s.text('f5guard',50,1440,2700,36,'待確認｜F5 pool/member 對應、既有連線與等待上限、健康門檻、控制身分／位置；不預設 Disabled／Forced Offline。檔案復原 ≠ 資料庫復原。',size=26,color=MUTED,align='left')
    s.text('legendheading',50,1500,120,38,'圖例',size=28,bold=True,align='left')
    # Legend sample arrows also use real editable source/target cells.
    for id,x,kind,color,label in [('lc',170,'control',BLUE,'控制／授權（虛線）'),('ld',660,'data',BLUE,'程式碼／產物（實線）'),('lt',1190,'traffic',TEAL,'應用流量（粗線）')]:
        s.text(id+'a',x,1514,1,1,'')
        s.text(id+'b',x+100,1514,1,1,'')
        s.edge(id,id+'a',id+'b',[(x,1514),(x+100,1514)],kind=kind,color=color)
        s.text(id+'label',x+115,1495,390,38,label,size=26,align='left')
    s.text('footer',1740,1488,1010,65,'分區是責任邊界，非已驗證網段／ACL • 接收器與部署腳本待實作\n可編輯主檔：draw.io；生成器僅初始種子，簡報重建不覆寫手改',size=26,color=MUTED,align='right')
    return s


def split_scenes(scene):
    """Standalone views; keep actual editable cells and connected terminals."""
    architecture = Scene(width=W, height=990)
    lifecycle = Scene(width=W, height=695)
    for destination, select, offset in [
        (architecture, lambda n: n.y < 900 or n.y >= 1488,
         lambda n: -590 if n.y >= 1488 else 0),
        (lifecycle, lambda n: n.y >= 900, lambda n: -880),
    ]:
        shifts = {}
        for n in scene.nodes:
            if select(n):
                shifts[n.id] = offset(n)
                destination.nodes.append(replace(n, y=n.y + offset(n)))
        ids = set(shifts)
        for e in scene.edges:
            if e.source in ids and e.target in ids:
                assert shifts[e.source] == shifts[e.target], e.id
                destination.edges.append(replace(e, points=[(x, y + shifts[e.source]) for x, y in e.points]))
    for n in architecture.nodes:
        if n.id == 'title':
            n.text = 'Windows 正式部署｜端到端交付架構'
    for n in lifecycle.nodes:
        if n.id == 'lifetitle':
            n.text = '單台 Target｜換版與復原流程'
        elif n.id == 'footer':
            n.text = '適用於每一核准 Target • 已放行指定版本後才執行\n可編輯主檔：draw.io；此圖不代表已完成實機驗證'
    return architecture, lifecycle


def validate(scene):
    W, H = scene.width, scene.height
    ids={n.id for n in scene.nodes}
    assert len(ids)==len(scene.nodes)
    assert len({e.id for e in scene.edges})==len(scene.edges)
    assert not ids.intersection(e.id for e in scene.edges)
    for n in scene.nodes:
        assert 0 <= n.x <= n.x+n.w <= W and 0 <= n.y <= n.y+n.h <= H, n.id
        assert n.parent == '1' or n.parent in ids, n.id
        if n.text:
            font=FONT+'Bold' if n.bold else FONT
            for line in n.text.split('\n'):
                width=pdfmetrics.stringWidth(line,font,n.size)
                assert width <= n.w - (24 if n.kind=='box' else 0), (n.id,line,width,n.w)
            assert len(n.text.split('\n'))*n.size*1.22 <= n.h, n.id
    nodes = {n.id: n for n in scene.nodes}
    for n in scene.nodes:
        if n.parent != '1':
            p = nodes[n.parent]
            assert p.x <= n.x and p.y <= n.y, (n.id, 'parent origin')
            assert n.x+n.w <= p.x+p.w and n.y+n.h <= p.y+p.h, (n.id, 'parent bounds')
    for e in scene.edges:
        assert e.source in ids and e.target in ids, e.id
        assert all(0<=x<=W and 0<=y<=H for x,y in e.points), e.id
        for (x1,y1),(x2,y2) in zip(e.points,e.points[1:]):
            assert x1 == x2 or y1 == y2, (e.id, 'non-orthogonal segment')
            for n in scene.nodes:
                if n.kind not in ('box','diamond') or n.id in (e.source,e.target):
                    continue
                crosses = ((x1 == x2 and n.x < x1 < n.x+n.w and max(min(y1,y2),n.y) < min(max(y1,y2),n.y+n.h)) or
                           (y1 == y2 and n.y < y1 < n.y+n.h and max(min(x1,x2),n.x) < min(max(x1,x2),n.x+n.w)))
                assert not crosses, (e.id, 'crosses node', n.id)


def drawio(scene, path):
    W, H = scene.width, scene.height
    # mxCodec uses an Array as its ID cache. Bare names such as "push"
    # resolve to inherited functions, causing obj.setId is not a function.
    # Namespace every custom cell ID and every reference, retaining roots 0/1.
    def cell_id(value):
        return value if value in ('0', '1') else 'wdm-' + value

    root=ET.Element('mxfile',host='app.diagrams.net',type='device')
    diagram=ET.SubElement(root,'diagram',name=path.stem,id=path.stem)
    model=ET.SubElement(diagram,'mxGraphModel',dx=str(W),dy=str(H),grid='1',gridSize='10',page='1',pageScale='1',pageWidth=str(W),pageHeight=str(H),background='#FFFFFF')
    cells=ET.SubElement(model,'root')
    ET.SubElement(cells,'mxCell',id='0')
    ET.SubElement(cells,'mxCell',id='1',parent='0')
    nodes={n.id:n for n in scene.nodes}
    for n in scene.nodes:
        shape={'text':'text','diamond':'rhombus'}.get(n.kind,'rectangle')
        fill='none' if n.kind=='text' else n.fill
        stroke='none' if n.kind=='text' else n.stroke
        style=f'shape={shape};rounded=1;arcSize=12;whiteSpace=wrap;html=0;fontFamily=Microsoft JhengHei;fontSize={n.size};fontColor={n.color};fontStyle={1 if n.bold else 0};fillColor={fill};strokeColor={stroke};strokeWidth=2;align={n.align};verticalAlign=middle;spacing=0;spacingLeft={12 if n.kind=="box" and n.align=="left" else 0};'
        if n.kind=='container':
            style+='container=1;collapsible=0;recursiveResize=0;'
        cell=ET.SubElement(cells,'mxCell',id=cell_id(n.id),value=n.text,style=style,vertex='1',parent=cell_id(n.parent))
        parent=nodes.get(n.parent)
        ET.SubElement(cell,'mxGeometry',x=str(n.x-(parent.x if parent else 0)),y=str(n.y-(parent.y if parent else 0)),width=str(n.w),height=str(n.h),attrib={'as':'geometry'})
    for e in scene.edges:
        source,target=nodes[e.source],nodes[e.target]
        sx,sy=e.points[0];tx,ty=e.points[-1]
        width=5 if e.kind=='traffic' else 3
        style=f'edgeStyle=none;rounded=0;html=0;endArrow=block;endFill=1;strokeColor={e.color};strokeWidth={width};dashed={1 if e.kind=="control" else 0};dashPattern=8 5;exitX={(sx-source.x)/source.w};exitY={(sy-source.y)/source.h};exitPerimeter=0;entryX={(tx-target.x)/target.w};entryY={(ty-target.y)/target.h};entryPerimeter=0;'
        cell=ET.SubElement(cells,'mxCell',id=cell_id(e.id),style=style,edge='1',parent='1',source=cell_id(e.source),target=cell_id(e.target))
        geom=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
        if len(e.points)>2:
            arr=ET.SubElement(geom,'Array',attrib={'as':'points'})
            for x,y in e.points[1:-1]:
                ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
    ET.indent(root)
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    parsed=ET.parse(path)
    all_ids={c.get('id') for c in parsed.findall('.//mxCell')}
    for c in parsed.findall('.//mxCell'):
        for key in ('source','target','parent'):
            if c.get(key):
                assert c.get(key) in all_ids, (c.get('id'),key)


def pdf(scene, path):
    W, H = scene.width, scene.height
    c=canvas.Canvas(str(path),pagesize=(W,H),pageCompression=1)
    title = next(n.text for n in scene.nodes if n.id in ('title', 'lifetitle'))
    c.setTitle(title)
    c.setAuthor('Architecture planning')
    # Zones first, then edges, then content: text stays legible over routes.
    def shape(n):
        if n.kind=='text': return
        c.setFillColor(HexColor(n.fill));c.setStrokeColor(HexColor(n.stroke));c.setLineWidth(2);c.setDash()
        if n.kind=='diamond':
            p=c.beginPath();p.moveTo(n.x+n.w/2,H-n.y)
            p.lineTo(n.x+n.w,H-n.y-n.h/2);p.lineTo(n.x+n.w/2,H-n.y-n.h);p.lineTo(n.x,H-n.y-n.h/2);p.close()
            c.drawPath(p,stroke=1,fill=1)
        else:
            c.roundRect(n.x,H-n.y-n.h,n.w,n.h,12,stroke=1,fill=1)
    for n in scene.nodes:
        if n.kind=='container': shape(n)
    for e in scene.edges:
        c.setStrokeColor(HexColor(e.color));c.setFillColor(HexColor(e.color));c.setLineWidth(5 if e.kind=='traffic' else 3)
        c.setDash([8,5] if e.kind=='control' else [])
        p=c.beginPath();p.moveTo(e.points[0][0],H-e.points[0][1])
        for x,y in e.points[1:]:p.lineTo(x,H-y)
        c.drawPath(p)
        x,y=e.points[-1];px,py=e.points[-2];a=math.atan2(y-py,x-px)
        p=c.beginPath();p.moveTo(x,H-y)
        for angle in (a-0.45,a+0.45):p.lineTo(x-14*math.cos(angle),H-y+14*math.sin(angle))
        p.close();c.setDash();c.drawPath(p,stroke=0,fill=1)
    for n in scene.nodes:
        if n.kind!='container':shape(n)
        if not n.text:continue
        c.setFont(FONT+'Bold' if n.bold else FONT,n.size);c.setFillColor(HexColor(n.color))
        lines=n.text.split('\n');leading=n.size*1.22
        y=n.y+(n.h-leading*len(lines))/2+n.size*0.94
        for line in lines:
            if n.align=='left':c.drawString(n.x+(12 if n.kind=='box' else 0),H-y,line)
            elif n.align=='right':c.drawRightString(n.x+n.w,H-y,line)
            else:c.drawCentredString(n.x+n.w/2,H-y,line)
            y+=leading
    c.showPage();c.save()


def main():
    fonts=Path('C:/Windows/Fonts')
    pdfmetrics.registerFont(TTFont(FONT,str(fonts/'msjh.ttc'),subfontIndex=0))
    pdfmetrics.registerFont(TTFont(FONT+'Bold',str(fonts/'msjhbd.ttc'),subfontIndex=0))
    scene=make_scene()
    architecture, lifecycle = split_scenes(scene)
    OUT.mkdir(parents=True,exist_ok=True)
    for name, view in [('windows-deployment-map', scene),
                       ('windows-deployment-architecture', architecture),
                       ('windows-target-release-flow', lifecycle)]:
        validate(view)
        base=OUT/name
        drawio(view,base.with_suffix('.drawio'))
        pdf(view,base.with_suffix('.pdf'))
        with fitz.open(base.with_suffix('.pdf')) as doc:
            assert len(doc)==1
            assert not doc[0].get_images(), 'PDF must remain vector'
            doc[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(base.with_suffix('.png'))
        print(f'Validated {len(view.nodes)} nodes, {len(view.edges)} edges; '
              f'{view.width}x{view.height}; vector PDF; {base}')


if __name__=='__main__':
    main()
