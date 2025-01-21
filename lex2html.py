#!/usr/bin/env python3
#
# setup:
# pip install Jinja2

import json
import logging
import os

import jinja2
#import Environment, PackageLoader

logger = logging.getLogger(__name__)

je = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
)

knownDefTypes = {
    # "concrete"
    'null',
    'boolean',
    'integer',
    'string',
    'bytes',
    'cid-link',
    'blob',

    # "container"
    'array',
    'object',
    'params',

    # "meta"
    'token',
    'ref',
    'union',
    'unknown',

    # "primary"
    'record',
    'query',
    'procedure',
    'subscription',
}

typeSubfields = {
    "record": ["key", "record"],
    "query": ["parameters", "output", "input", "errors"],
    "procedure": ["parameters", "output", "input", "errors"],
    "subscription": ["parameters", "message", "errors"],
    "null": [],
    "boolean": ["default", "const"],
    "integer": ["minimum", "maximum", "enum", "default", "const"],
    "string": ["format", "maxLength", "minLength", "maxGraphemes", "minGraphemes", "knownValues", "enum", "default", "const"],
    "bytes": ["minLength", "maxLength"],
    "cid-link": [],
    "array": ["items", "minLength", "maxLength"],
    "object": ["properties", "required", "nullable"],
    "blob": ["accept", "maxSize"],
    "params": ["required", "properties"],
    "token": [],
    "ref": ["ref"],
    "union": ["refs", "closed"],
    "unknown": [],
}

def dnset(d, k, v):
    # dict set, but only if value is not None
    if v is not None:
        d[k] = v

def pathget(d, *args):
    # walk nested dict keys, bailing at any None
    for k in args:
        d = d.get(k)
        if d is None:
            return None
    return d

def refToAbsoluteRef(ref, lastdefid):
    if ref[0] == '#':
        if '#' in lastdefid:
            root, rest = lastdefid.split('#')
            ref = root + ref
        else:
            ref = lastdefid + ref
    return ref

def defidToFragment(defid):
    # com.atproto.server.createAppPassword#appPassword -> com.atproto.server.createAppPassword_appPassword
    return defid.replace('#', '_')

class LexSet:
    def __init__(self, args):
        self.args = args
        self.idToFile = {}
        self.totSize = 0
        self.found = []
        self.idToDef = {}
        self.outsets = {}
        self.allchunks = []
        self.allrefs = []
        self.defidstack = []

    def addPath(self, fpath):
        # do a quick first read of a lexicon file
        fsize = os.path.getsize(fpath)
        logger.debug("%9d %s", fsize, fpath)
        with open(fpath, 'rt') as fin:
            ob = json.load(fin)
        fid = None
        description = None
        hasDefs = False
        for k, v in ob.items():
            if k == 'lexicon':
                assert v == 1
            elif k == 'id':
                fid = v
            elif k == 'defs':
                hasDefs = True
            elif k == 'description':
                description = v
            elif k == 'revision':
                pass # ignore
            else:
                logger.error("%s: unknown key %r", fpath, k)
                return
        if not hasDefs:
            logger.error("%s: no defs", fpath)
            return
        if not fid:
            logger.error("%s: no id", fpath)
            return
        if fid in self.idToFile:
            logger.error("%s: dup id %r already seen at %s", fpath, fid, self.idToFile[fid])
            return
        self.idToFile[fid] = fpath
        self.found.append(fpath)
        self.totSize += fsize

    def ingestAll(self):
        for fpath in self.found:
            self.ingest(fpath)

    def ingest(self, fpath):
        with open(fpath, 'rt') as fin:
            ob = json.load(fin)
        defs = ob['defs']
        fid = ob['id']
        outset = []
        for k, v in defs.items():
            if k == 'main':
                defid = fid
            else:
                defid = fid + '#' + k
            ok = self.ingestDef(fpath, defid, v)
            if ok:
                outset.append((defid, v))
        if outset:
            xrec = dict(ob)
            xrec['defs'] = outset
            self.outsets[fpath] = xrec
    def ingestDef(self, fpath, defid, defo):
        dtype = defo.get('type')
        if dtype is None:
            logger.error("%s: %s no type", fpath, defid)
            return False
        if dtype not in knownDefTypes:
            logger.error("%s: %s unknown def type %r", fpath, defid, v)
            return False
        desc = defo.get('description')
        okSubs = typeSubfields[dtype]
        for k,v in defo.items():
            if k == 'type':
                pass
            elif k == 'description':
                pass
            elif k in okSubs:
                pass
            else:
                logger.error("%s: %s unknown sub field %r", fpath, defid, k)
                return False
        defo['defid'] = defid
        defo['defidName'] = defidToFragment(defid)
        self.idToDef[defid] = defo
        return True
    def recHtmlSubfield(self, lexrec, hlevel, k, path=None, **kwargs):
        if path is not None:
            subf = pathget(lexrec, *path)
        else:
            subf = lexrec.get(k)
        if subf is None:
            return
        try:
            html = self.renderRec(subf, **kwargs)
        except Exception as e:
            raise Exception(f"subfield {k!r} failed: {e}")
        lexrec[k+'_html'] = html
    def renderRec(self, lexrec, hlevel=2, **kwargs):
        defid = lexrec.get('defid')
        if defid:
            self.defidstack.append(defid)
        rectype = lexrec['type']
        recTmpl = je.get_template(rectype+".html")
        # recursion step, render sub-objects to {foo}_html
        if rectype == 'query':
            self.recHtmlSubfield(lexrec, hlevel+1, 'parameters', suppressType=True)
            self.recHtmlSubfield(lexrec, hlevel+1, 'output', path=('output', 'schema'), suppressType=True)
        elif rectype == 'record':
            self.recHtmlSubfield(lexrec, hlevel+1, 'record')
        elif rectype == 'procedure':
            self.recHtmlSubfield(lexrec, hlevel+1, 'parameters', suppressType=True)
            self.recHtmlSubfield(lexrec, hlevel+1, 'input', path=('input', 'schema'), suppressType=True)
            self.recHtmlSubfield(lexrec, hlevel+1, 'output', path=('output', 'schema'), suppressType=True)
        elif rectype == 'subscription':
            self.recHtmlSubfield(lexrec, hlevel+1, 'parameters', suppressType=True)
            self.recHtmlSubfield(lexrec, hlevel+1, 'message', path=('message', 'schema'), suppressType=True)
        elif rectype == 'array':
            self.recHtmlSubfield(lexrec, hlevel+1, 'items')
        elif rectype == 'object':
            xrequired = lexrec.get('required', [])
            xnullable = lexrec.get('nullable', [])
            properties = lexrec.get('properties')
            if properties:
                ph = {}
                for k,v in properties.items():
                    html = self.renderRec(v,hlevel+1)
                    if k in xrequired:
                        html = '<span class="required">required</span> ' + html
                    if k in xnullable:
                        html = '<span class="nullable">nullable</span> ' + html
                    ph[k] = html
                lexrec['properties_html'] = ph
        elif rectype == 'params':
            xrequired = lexrec.get('required', [])
            properties = lexrec.get('properties')
            if properties:
                ph = {}
                for k,v in properties.items():
                    html = self.renderRec(v,hlevel+1)
                    if k in xrequired:
                        html = '<span class="required">required</span> ' + html
                    ph[k] = html
                lexrec['properties_html'] = ph
        elif rectype == 'ref':
            ref = lexrec['ref']
            ref = refToAbsoluteRef(ref, self.defidstack[-1])
            lexrec['refName'] = defidToFragment(ref)
        elif rectype == 'union':
            refs = lexrec['refs']
            refs_html = [(ref, defidToFragment(refToAbsoluteRef(ref, self.defidstack[-1]))) for ref in refs]
            lexrec['refs_html'] = refs_html
        rdict = dict(kwargs)
        rdict["xobject"] = lexrec
        rdict["hlevel"] = hlevel
        html = recTmpl.render(rdict)
        if defid:
            self.defidstack.pop()
        return html
    def renderHtml(self):
        if self.args.out == "":
            logger.warning("output dir is empty string, not rendering html")
            return
        for fpath, xrec in self.outsets.items():
            html = self.renderHtmlPage(fpath, xrec)
            if not args.all_only:
                if fpath.endswith('.json'):
                    fpath = fpath[:-5]
                fpath += '.html'
                outpath = os.path.join(self.args.out, fpath)
                logger.info("%9d %s", len(html), outpath)
                os.makedirs(os.path.dirname(outpath), exist_ok=True)
                with open(outpath, 'wt') as fout:
                    fout.write(html)

        # make all.html
        self.allrefs.sort()
        self.allchunks.sort()
        allchunks = [xc for (_, xc) in self.allchunks]
        pageTmpl = je.get_template('page.html')
        html = pageTmpl.render({"title":"all lexicons", "chunks":allchunks, "toc": self.allrefs})
        outpath = os.path.join(self.args.out, 'all.html')
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        logger.info("%9d %s", len(html), outpath)
        with open(outpath, 'wt') as fout:
            fout.write(html)
    def renderHtmlPage(self, fpath, xrec):
        chunks = []
        refs = []
        for defid, defo in xrec['defs']:
            #chunkTmpl = je.get_template(defo['type']+".html")
            #rdict = {"object":defo, "hlevel": 2}
            #chunkHtml = chunkTmpl.render(rdict)
            try:
                chunkHtml = self.renderRec(defo)
            except Exception as e:
                raise Exception(f"{fpath} {defid} failed: {e}")
            ref = (defid, defo['defidName'], defo['type'])
            refs.append(ref)
            self.allrefs.append(ref)
            chunks.append((defid,chunkHtml))
            self.allchunks.append((defid,chunkHtml))
        pageTmpl = je.get_template('page.html')
        refs.sort()
        chunks.sort()
        chunks = [xc for (_, xc) in chunks]
        return pageTmpl.render({"title":xrec["id"], "chunks":chunks, "toc": refs})

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='*', help='files to read and dirs to crawl for lexicon json; default to searching ./')
    ap.add_argument('-o', '--out', default='html', help='name of directory to output to, default ./html/')
    ap.add_argument('--all-only', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    paths = args.paths
    if not paths:
        paths = ['.']

    ls = LexSet(args)
    for inpath in paths:
        if os.path.isdir(inpath):
            for root, dirs, files in os.walk(inpath):
                for fname in files:
                    if fname.endswith('.json'):
                        fpath = os.path.join(root, fname)
                        ls.addPath(fpath)
    logger.info("found %d files, total %d bytes", len(ls.found), ls.totSize)
    ls.ingestAll()
    ls.renderHtml()
