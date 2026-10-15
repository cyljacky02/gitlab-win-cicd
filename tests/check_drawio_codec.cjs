/* Real mxGraph codec regression test (not just XML validation).
 * Setup: npm install --prefix .venv-slides/mermaid-check jsdom
 * Download upstream v4.2.2 javascript/mxClient.js from github.com/jgraph/mxgraph
 * to .venv-slides/mermaid-check/mxClient.js.
 * Run: node tests/check_drawio_codec.cjs
 * Optional: pass mxClient.js path, jsdom package path, then draw.io file paths.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const codecPath = path.resolve(process.argv[2] || '.venv-slides/mermaid-check/mxClient.js');
const jsdomPath = path.resolve(process.argv[3] || '.venv-slides/mermaid-check/node_modules/jsdom');
const {JSDOM} = require(jsdomPath);
const dom = new JSDOM('<html><body></body></html>', {runScripts: 'outside-only', url: 'https://example.test/'});
const w = dom.window;
w.mxLoadResources = false;
w.mxLoadStylesheets = false;
w.eval(fs.readFileSync(codecPath, 'utf8'));
function decode(xml) {
    const doc = w.mxUtils.parseXml(xml);
    assert.equal(doc.getElementsByTagName('parsererror').length, 0);
    const root = doc.getElementsByTagName('mxGraphModel')[0];
    assert.ok(root, 'mxGraphModel missing');
    const model = new w.mxGraphModel();
    new w.mxCodec(doc).decode(root, model);
    for (const cell of root.getElementsByTagName('mxCell')) {
        const actual = model.getCell(cell.getAttribute('id'));
        assert.ok(actual instanceof w.mxCell, 'not an mxCell: ' + cell.getAttribute('id'));
        for (const key of ['parent', 'source', 'target']) {
            if (cell.hasAttribute(key)) {
                const linked = key === 'parent' ? actual.getParent() : actual.getTerminal(key === 'source');
                assert.ok(linked, `${actual.id}: missing ${key}`);
                assert.equal(linked.getId(), cell.getAttribute(key));
            }
        }
    }
    assert.equal(Object.keys(model.cells).length, root.getElementsByTagName('mxCell').length);
    return model;
}
const minimal = '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="push" parent="1" vertex="1"/></root></mxGraphModel>';
assert.throws(() => decode(minimal), /setId is not a function/, 'fixture must reproduce the reported error');
decode(minimal.replace('id="push"', 'id="map-push"'));
const files = process.argv.slice(4);
if (!files.length) files.push(...fs.readdirSync('docs/presentations/diagrams').filter(f => f.endsWith('.drawio')).map(f => 'docs/presentations/diagrams/' + f));
for (const file of files) {
    const model = decode(fs.readFileSync(file, 'utf8'));
    const encoded = new w.mxCodec().encode(model);
    const roundtrip = decode(w.mxUtils.getXml(encoded));
    assert.equal(Object.keys(roundtrip.cells).length, Object.keys(model.cells).length);
    console.log(`PASS ${file}: ${Object.keys(model.cells).length} cells, links + codec roundtrip`);
}
dom.window.close();
