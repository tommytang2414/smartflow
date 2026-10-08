"""Disposable end-to-end rehearsal; no network, production writes or model calls."""
from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from smartflow.research.common import canonical, digest, file_hash, stamp, utc, write_json
from smartflow.research.evidence import aliases, security_key, select_events, source_assessments
from smartflow.research.model import validate_analysis, validate_review, run_model, object_schema, SAFE_DIAGNOSTICS, render_report
from smartflow.research.news import import_news
from smartflow.research.pack import build_pack, company_change
from smartflow.research.snapshots import BUCKET, KEYS, import_snapshot
from smartflow.research.store import ResearchStore
from smartflow.research.__main__ import analyze
from smartflow.research.insider import derive
from smartflow.research.company import fetch as fetch_company, load as load_company, visible_text
from smartflow.events import make_source_event_id


NOW = utc("2026-10-08T00:00:00Z")


def rejects(callback, expected):
    try:
        callback()
    except ValueError as error:
        assert expected in str(error), (expected, str(error))
    else:
        raise AssertionError("expected rejection: " + expected)


def event(source, identity, action="purchase", *, actor="1", title="Common Stock"):
    house = source == "congress"
    return dict(source=source, source_event_id=identity, event_type="congress_periodic_transaction" if house else "form4_transaction",
                action=action, side="BUY" if action == "purchase" else "SELL", execution_status="reported", market="US",
                security_id="US:ACME" if house else "0000000001", ticker="ACME", entity_id=actor if house else None,
                entity_name=None, entities=[] if house or not actor else [{"entity_cik": actor}],
                attributes={"asset_type": "ST", "amount_lower": "1001", "amount_upper": "15000"} if house else
                {"instrument_type": "non_derivative", "transaction_code": "P" if action == "purchase" else "S", "security_title": title},
                quantity=None if house else "10", price=None if house else "100", value=None if house else "1000", currency="USD",
                event_at=stamp(NOW-timedelta(days=1)), filed_at=stamp(NOW), observed_at=stamp(NOW),
                source_url="https://disclosures-clerk.house.gov/sample.pdf" if house else "https://www.sec.gov/Archives/sample.xml",
                parser_version="congress-house-ptr-v4" if house else "sec-form4-v4", quality_status="valid", quality_reasons=[])


def snapshot(root, group, events):
    path = root / (group + ".db")
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE raw_events(id INTEGER PRIMARY KEY,source TEXT,source_event_id TEXT,payload TEXT,payload_sha256 TEXT);
    CREATE TABLE normalized_events_v2(id INTEGER PRIMARY KEY,source TEXT,source_event_id TEXT,event_type TEXT,action TEXT,side TEXT,
      execution_status TEXT,market TEXT,security_id TEXT,ticker TEXT,entity_id TEXT,entity_name TEXT,entities TEXT,attributes TEXT,
      quantity NUMERIC,price NUMERIC,value NUMERIC,currency TEXT,event_at TEXT,filed_at TEXT,observed_at TEXT,source_url TEXT,
      raw_event_id INTEGER REFERENCES raw_events(id),parser_version TEXT,quality_status TEXT,quality_reasons TEXT);
    CREATE TABLE collector_runs_v2(id INTEGER PRIMARY KEY,collector TEXT,started_at TEXT,status TEXT,failure_kind TEXT,details TEXT);
    CREATE TABLE source_health(source TEXT PRIMARY KEY,state TEXT,reason TEXT,last_run_status TEXT,last_failure_kind TEXT,
      checked_at TEXT,last_run_at TEXT,last_success_at TEXT,last_event_at TEXT);
    """)
    for index, body in enumerate(events, 1):
        payload = {"fixture": body["source_event_id"]}
        db.execute("INSERT INTO raw_events VALUES(?,?,?,?,?)", (index,body["source"],body["source_event_id"],canonical(payload).decode(),digest(canonical(payload))))
        fields = {**body, "id":index,"raw_event_id":index}
        for name in ("entities","attributes","quality_reasons"):
            fields[name]=canonical(fields[name]).decode()
        db.execute("INSERT INTO normalized_events_v2("+",".join(fields)+") VALUES("+",".join("?" for _ in fields)+")", list(fields.values()))
    for source in sorted({body["source"] for body in events}):
        interval = 300 if source == "sec_form4" else 3600
        for index in range(14*86400//interval):
            db.execute("INSERT INTO collector_runs_v2(collector,started_at,status,details) VALUES(?,?,'success',?)",
                       (source,stamp(NOW-timedelta(seconds=index*interval)),canonical({"reports_remaining":0}).decode()))
        db.execute("INSERT INTO source_health VALUES(?,'healthy','fixture','success',NULL,?,?,?,?)", (source,*([stamp(NOW)]*4)))
    db.commit()
    db.close()
    return path,dict(bucket=BUCKET,key=KEYS[group],version_id="fixture-version",sha256=file_hash(path),generated_at=stamp(NOW),size_bytes=path.stat().st_size,file=path.name)


def check_us_context(root):
    # A skipped XML row and an accepted derivative precede the target. Matching
    # raw ordinal instead of the production accepted index would select wrongly.
    xml='''<ownershipDocument><issuer><issuerCik>1</issuerCik></issuer><aff10b5One>true</aff10b5One>
    <nonDerivativeTransaction/><nonDerivativeTransaction><transactionAmounts><transactionShares><value>invalid</value></transactionShares></transactionAmounts></nonDerivativeTransaction>
    <derivativeTransaction><transactionAmounts><transactionShares><value>3</value></transactionShares></transactionAmounts></derivativeTransaction>
    <nonDerivativeTransaction><securityTitle><value>Common Stock</value></securityTitle><transactionDate><value>2026-10-07</value></transactionDate>
    <transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionAmounts><transactionShares><value>10</value></transactionShares>
    <transactionPricePerShare><value>100</value><footnoteId id="F1"/></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
    <postTransactionAmounts><sharesOwnedFollowingTransaction><value>110</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction>
    <footnotes><footnote id="F1">Weighted average price; multiple transactions.</footnote></footnotes></ownershipDocument>'''
    transaction=event('sec_form4','unused');transaction.update(raw_identity='0000000001-26-000001',raw_hash='f'*64)
    transaction['attributes']['acquired_disposed']='A'
    transaction['source_event_id']=make_source_event_id('sec_form4',transaction['raw_identity'],1)
    context=derive(transaction,xml)
    assert context['status']=='MATCHED' and context['xml_transaction_ordinal']==3 and context['accepted_transaction_index']==1
    assert context['holdings_after']=='110' and context['filing_plan_indicator'] is True and context['position_percentage'] is None
    assert context['field_footnotes']['price'][0]['text'].startswith('Weighted average')
    assert derive({**transaction,'quantity':'11'},xml)['status']=='UNKNOWN_TRANSACTION_MATCH'
    assert derive(transaction,xml.replace('<aff10b5One>true</aff10b5One>',''))['filing_plan_indicator'] is None
    conflict=derive(transaction,xml.replace('Weighted average price','Weighted average sale price'))
    assert conflict['source_note_warnings']==['FOOTNOTE_SALE_PRICE_WORDING_WITH_P_CODE']
    rejects(lambda:derive(transaction,'<!DOCTYPE x>'+xml),'unsafe_form4')
    definitions=[dict(security_key='US:ACME:COMMON',issuer_cik='0000000001',market='US',ticker='ACME')]
    submissions=dict(cik=1,tickers=['ACME'],name='Acme',filings=dict(recent=dict(form=['8-K'],accessionNumber=['0000000001-26-000001'],
        primaryDocument=['report.htm'],filingDate=['2026-10-07'],reportDate=['2026-10-06'],acceptanceDateTime=['2026-10-07T19:00:00Z'],items=['2.02'])))
    html=b'<html><head><title>Hidden</title></head><body><div style="display:none">Secret hidden</div><p>Item 2.02</p><p>'+b'Company outlook remains uncertain. '*30+b'</p></body></html>'
    assert 'Hidden' not in visible_text(html) and 'Secret hidden' not in visible_text(html)
    def reader(_,url):
        return canonical(submissions) if url.startswith('https://data.sec.gov/') else html
    bundle=root/'company-bundle'
    with patch('smartflow.research.company.SECReader.get',reader):
        assert fetch_company(definitions,bundle,'research@example.test')['documents']==1
    cutoff=utc(stamp())+timedelta(seconds=1)
    loaded=load_company(bundle,definitions,cutoff,root/'company-cache')
    assert len(loaded['by_security']['US:ACME:COMMON'])==1 and loaded['prices']['returns'] is None
    documents=loaded['by_security']['US:ACME:COMMON']
    refetched=copy.deepcopy(documents);refetched[0]['id']='Cnewreceipt';refetched[0]['retrieved_at']=stamp(cutoff)
    assert company_change(refetched,{'company_documents':documents})['status']=='UNCHANGED'
    assert company_change(refetched,{'company_documents':documents})['new_original_ids']==[]
    assert company_change(documents,{'company_documents':[]})['new_original_ids']==[documents[0]['id']]
    rejects(lambda:load_company(bundle,definitions,NOW,root/'future-cache'),'after_cutoff')
    manifest=json.loads((bundle/'manifest.json').read_text());doc=manifest['documents'][0]
    doc['excerpts'][0]['quote']='Invented issuer claim'
    doc['id']='C'+digest(canonical({k:v for k,v in doc.items() if k!='id'}))[:24]
    write_json(bundle/'manifest.json',manifest)
    rejects(lambda:load_company(bundle,definitions,cutoff,root/'tamper-cache'),'quote_mismatch')
    manifest['prices']['returns']='pretend prices';write_json(bundle/'manifest.json',manifest)
    rejects(lambda:load_company(bundle,definitions,cutoff,root/'price-cache'),'unverified_price_payload')


def main():
    checks=[]
    with tempfile.TemporaryDirectory(prefix="research-rehearsal-") as folder, ExitStack() as cleanup:
        root=Path(folder)
        check_us_context(root)
        checks.append('Form4 accepted-order/signature matching, plan unknown, footnote/holdings provenance and no position inference; SEC original/excerpt/cutoff/price fail closed')
        store=ResearchStore(root/"state")
        cleanup.callback(store.close)
        sec=[event("sec_form4","buy"),event("sec_form4","buy-again"),event("sec_form4","other-class",title="Class B Common Stock"),
             event("sec_form4","unknown",actor=None)]
        proposed=event("sec_form144","proposed",action="sale")
        proposed.update(event_type="form144_notice",action="proposed_sale",execution_status="proposed",parser_version="sec-form144-v1",event_at=stamp(NOW+timedelta(days=3)))
        sec.append(proposed)
        house=[event("congress","sale","sale",actor="member-household")]
        paths={}
        for group, bodies in (("sec",sec),("house",house)):
            path,manifest=snapshot(root,group,bodies)
            before=file_hash(path)
            assert import_snapshot(store,group,path,manifest,now=NOW)["inserted"] == len(bodies)
            assert import_snapshot(store,group,path,manifest,now=NOW)["inserted"] == 0
            assert file_hash(path)==before
            paths[group]=(path,manifest)
        checks.append("immutable versioned import, replay and source read-only")
        events,_=select_events(store,NOW)
        proof=next(e for e in events if e["source_event_id"]=="buy")
        definitions=[dict(security_key="US:ACME:COMMON",market="US",ticker="ACME",issuer_cik="0000000001",sec_titles=["Common Stock"],
                          valid_from=stamp(NOW-timedelta(days=10)),valid_to=stamp(NOW+timedelta(days=10)),proof_ids=[proof["id"]],company_terms=["Acme Corporation"])]
        validated=aliases(events,definitions)
        assert not security_key(next(e for e in events if e["source_event_id"]=="other-class"),validated)[1]
        invalid=copy.deepcopy(definitions);invalid[0]["sec_titles"].append("Class B Common Stock")
        rejects(lambda:aliases(events,invalid),"invalid_alias")
        pack=build_pack(store,definitions,as_of=NOW)
        assert all(s['window_days']==14 and utc(s['window_end'])-utc(s['window_start'])==timedelta(days=14) for s in pack['source_assessments'])
        joined=next(d for d in pack["dossiers"] if d["identity_resolved"])
        assert joined["stance"]=="MIXED" and joined["distinct_actors"]==2 and joined["unknown_actor_events"]==1
        assert pack["bootstrap"] and joined["new_evidence_count"]==0
        assert next(d for d in pack["dossiers"] if any(e["action"]=="proposed_sale" for e in d["evidence"]))["stance"]=="CONTEXT_ONLY"
        checks.append("cross-source contradiction, actor dedup, unknown actors, class separation and future intent")
        path,manifest=paths["house"]
        corrupted=copy.deepcopy(manifest);corrupted["sha256"]="0"*64
        rejects(lambda:import_snapshot(store,"house",path,corrupted,now=NOW),"snapshot_hash_mismatch")
        db=sqlite3.connect(path);db.execute("UPDATE raw_events SET payload=?,payload_sha256=?", ('{"changed":true}',digest(canonical({"changed":True}))));db.commit();db.close()
        changed={**manifest,"version_id":"changed-version","sha256":file_hash(path),"size_bytes":path.stat().st_size}
        rejects(lambda:import_snapshot(store,"house",path,changed,now=NOW),"immutable_raw_identity_conflict")
        assert store.status()["imports"]==2
        checks.append("hash tamper and conflicting immutable identity roll back")
        assert all(not s["eligible_for_current_research"] for s in source_assessments(store,NOW+timedelta(days=2)))
        checks.append("fresh download cannot revive an old healthy snapshot")
        newsroot=root/"news";newsroot.mkdir()
        db=sqlite3.connect(newsroot/"newsroom.sqlite3")
        db.execute("CREATE TABLE documents(id INTEGER,source_id TEXT,url TEXT,title TEXT,published_at TEXT,retrieved_at TEXT,raw_hash TEXT,text_hash TEXT,raw_path TEXT,text_path TEXT)")
        for index,day in ((1,-1),(2,1)):
            text=b"Acme Corporation official original"
            (newsroot/f"{index}.txt").write_bytes(text)
            published="Wed, 07 Oct 2026 08:00:00 +0800" if index==1 else stamp(NOW+timedelta(days=day))
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",(index,"official","https://example.test/original","Acme Corporation",published,stamp(NOW+timedelta(days=day)),digest(text),digest(text),f"{index}.txt",f"{index}.txt"))
        db.commit();db.close();before=file_hash(newsroot/"newsroom.sqlite3")
        news=import_news(newsroot,definitions,NOW)
        assert [e["document_id"] for e in news["by_security"]["US:ACME:COMMON"]]==[1]
        assert news["by_security"]["US:ACME:COMMON"][0]["published_at"]=="2026-10-07T00:00:00+00:00"
        assert before==file_hash(newsroot/"newsroom.sqlite3")
        checks.append("newsroom original hashes, historical cutoff and zero DB writes")
        analysis=dict(pack_sha256=digest(canonical(pack)),overview="只供研究。",items=[dict(security_key=d["security_key"],summary="保留證據矛盾。",change_since_previous="首次匯入未有上次結論。",claims=[dict(kind="FACT",text="披露原件提供研究依據。",evidence_ids=[d["evidence"][0]["id"]])],counterevidence_ids=[],questions=["交易動機有冇其他解釋？"],
             thesis=dict(status='CONTESTED',hypothesis='披露方向未確立基本面改善。',support_ids=[d['evidence'][0]['id']],counter_ids=[],invalidation_condition='若出現已核實同 actor 的相反交易，重評方向。',next_evidence='下一份可核實交易原件。')) for d in pack["dossiers"]])
        validate_analysis(pack,analysis)
        render_pack=copy.deepcopy(pack)
        context=next(e['insider_context'] for d in render_pack['dossiers'] for e in d['evidence'] if e.get('insider_context'))
        context['field_footnotes']={'price':[{'id':'F1','text':'Disclosed price note'}], 'ownership':[{'id':'F2','text':'Disclosed ownership note'}]}
        rendered=render_report(render_pack,analysis,status='fixture')
        assert rendered==render_report(json.loads(canonical(render_pack)),json.loads(canonical(analysis)),status='fixture')
        bad=copy.deepcopy(analysis);bad["items"][0]["claims"][0]["evidence_ids"]=["Eunknown"]
        rejects(lambda:validate_analysis(pack,bad),"unknown_evidence")
        bad=copy.deepcopy(analysis);bad["overview"]="估計金額7500美元"
        rejects(lambda:validate_analysis(pack,bad),"numeric_prose")
        bad=copy.deepcopy(analysis);bad['items'][0]['thesis']['support_ids']=['Cunknown']
        rejects(lambda:validate_analysis(pack,bad),'thesis_unknown_evidence')
        review=dict(pack_sha256="a"*64,analysis_sha256="b"*64,report_sha256="c"*64,verdict="PASS_WITH_LIMITATIONS",findings="已核對證據。",limitations=["未有完整新聞覆蓋。"])
        validate_review(review)
        rejects(lambda:validate_review({**review,"findings":None}),"findings_invalid")
        assert store.status()["open_tasks"]==0 and not store.db.execute("SELECT 1 FROM analyzed").fetchone()
        checks.append("unknown citations, invented amounts, malformed review fail closed without advancing history")
        alias_path=root/"aliases.json";write_json(alias_path,definitions)
        def rejected_model(executable,directory,role,payload,schema,**kwargs):
            if role.startswith("analyst"):
                return analysis,{"thread_id":"analyst"}
            return {**review,"pack_sha256":payload["pack_sha256"],"analysis_sha256":payload["analysis_sha256"],
                    "report_sha256":payload["report_sha256"],"verdict":"BLOCKED"},{"thread_id":"reviewer"}
        with patch("smartflow.research.__main__.run_model",rejected_model):
            rejects(lambda:analyze(store,alias_path,Path("unused"),NOW,None),"independent_review_rejected")
        assert not store.db.execute("SELECT 1 FROM analyzed").fetchone()
        assert store.status()["runs"][0]["status"]=="needs_attention"
        checks.append("blocked independent reviewer prevents approval and preserves retry evidence")
        approved=root/"state"/"runs"/"approved-fixture";approved.mkdir()
        (approved/"ANALYSIS.json").write_bytes(canonical(analysis))
        (approved/"REPORT.md").write_text("Frozen verified fixture",encoding="utf-8")
        write_json(approved/"manifest.json",{"files":{name:file_hash(approved/name) for name in ("ANALYSIS.json","REPORT.md")}})
        with store.db:
            store.db.execute("INSERT INTO runs(id,pack_hash,directory,status) VALUES('approved-fixture','fixture','runs/approved-fixture','analyzing')")
        store.approve("approved-fixture",pack,analysis,file_hash(approved/"REPORT.md"),"review-fixture",file_hash(approved/"manifest.json"))
        assert store.previous(joined["security_key"])
        (approved/"REPORT.md").write_text("tampered",encoding="utf-8")
        rejects(lambda:store.previous(joined["security_key"]),"previous_approved_artifact_tamper")
        checks.append("approved history is bound to immutable report manifest and rejects later tamper")
        class SimulatedCLI:
            returncode=0
            def __init__(self,command,**kwargs):
                output=Path(command[command.index("--output-last-message")+1]);write_json(output,{"ok":True})
            def communicate(self,*args,**kwargs):
                stream=[{"type":"thread.started","thread_id":"isolated-fixture"},*self.items,{"type":"turn.completed","usage":{}}]
                return "\n".join(json.dumps(row) for row in stream),""
        schema=object_schema({"ok":{"type":"boolean"}})
        modelroot=root/"model";modelroot.mkdir()
        SimulatedCLI.items=[{"type":"item.completed","item":{"type":"command_execution","command":"forbidden"}}]
        with patch("smartflow.research.model.subprocess.Popen",SimulatedCLI):
            rejects(lambda:run_model(Path("unused"),modelroot,"tool",{},schema),"model_execution_not_verified")
            SimulatedCLI.items=[{"type":"item.completed","item":{"type":"error","message":"unknown runtime fault"}}]
            rejects(lambda:run_model(Path("unused"),modelroot,"fault",{},schema),"model_execution_not_verified")
            SimulatedCLI.items=[{"type":"item.completed","item":{"type":"error","message":next(iter(SAFE_DIAGNOSTICS))}}]
            result,receipt=run_model(Path("unused"),modelroot,"disabled-capability",{},schema)
            assert result=={"ok":True} and receipt["tool_item_count"]==0 and receipt["warning_codes"]==["CODE_MODE_HOST_DISABLED"]
        checks.append("actual tool events and unknown CLI errors reject; exact disabled-capability diagnostic is classified separately")
    print(json.dumps({"status":"PASS","checks":checks},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
