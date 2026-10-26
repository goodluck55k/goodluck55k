"""Authenticated real-API checks and stateless GitHub Markdown rendering.

No repository write endpoints, uploads, git commands or credential extraction.
"""
import datetime as dt
from html.parser import HTMLParser
import json
from common import ROOT,config,read_json,write_json,write_text
from collect import Client,DataError,star_data
from github_cli import GhTransport,login_status


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pictures=0
        self.sources=[]
        self.images=[]
        self.links=[]
        self.active_links=[]
        self.links_containing_images=set()

    def handle_starttag(self,tag,attributes):
        a=dict(attributes)
        if tag=="picture":
            self.pictures+=1
        elif tag=="source":
            self.sources.append(a)
        elif tag=="img":
            self.images.append(a)
            self.links_containing_images.update(self.active_links)
        elif tag=="a":
            self.links.append(a.get("href"))
            self.active_links.append(a.get("href"))

    def handle_endtag(self,tag):
        if tag=="a" and self.active_links:
            self.active_links.pop()


def main():
    status=login_status()
    if not status.get("logged_in"):
        raise SystemExit("GitHub CLI login is required. Complete the browser authorization yourself; no credential is needed in chat.")
    c=config()
    transport=GhTransport()
    results={"checked_at":dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),"login":status.get("login"),"remote_repository_writes":False,"checks":{}}
    try:
        rate=transport.call("/rate_limit")
        results["checks"]["rate_limit"]={"state":"ok","core":rate["resources"]["core"],"graphql":rate["resources"]["graphql"]}
    except DataError as error:
        results["checks"]["rate_limit"]={"state":"failed","reason":str(error)}
    # Verify the real zero-star endpoint too; a metadata zero is not an API failure.
    name=c["user"]+"/human-talk-checker"
    try:
        stars=transport.call(f"/repos/{name}/stargazers?per_page=100",accept="application/vnd.github.star+json")
        results["checks"]["user_star_history_endpoint"]={"state":"ok","repository":name,"returned":len(stars),"timestamp_fields_present":all("starred_at" in row for row in stars)}
    except DataError as error:
        results["checks"]["user_star_history_endpoint"]={"state":"failed","reason":str(error)}
    # Independently exercise the non-zero history path on a reference project.
    # Its data is NEVER put into this user's profile caches.
    try:
        meta=transport.call("/repos/DRAG0NM/Pare")
        if meta["stargazers_count"]>0:
            client=Client("gh-managed")
            client.request=transport.call
            row={"name":meta["name"],"full_name":meta["full_name"],"created_at":meta["created_at"],"stars":meta["stargazers_count"],"fork":meta["fork"]}
            data=star_data(client,[row])
            series=data["series"][0]
            results["checks"]["reference_nonzero_stars"]={"state":series["history_state"],"reason":series.get("reason"),"repository":meta["full_name"],"snapshot":meta["stargazers_count"],"events":len(series["starred_at"]),"sample_dates":series["starred_at"][:3],"not_used_in_profile":True}
            if series["history_state"]!="ok":
                diagnostic={}
                try:
                    default=transport.call(f"/repos/{meta['full_name']}/stargazers?per_page=100",accept="application/vnd.github.star+json")
                    diagnostic["rest_default_first_page"]={"count":len(default),"dates":[r.get("starred_at") for r in default[:3]]}
                except DataError as error:
                    diagnostic["rest_default_first_page"]={"error":str(error)}
                query="""query($owner:String!,$name:String!){repository(owner:$owner,name:$name){stargazerCount stargazers(first:100,orderBy:{field:STARRED_AT,direction:ASC}){totalCount edges{starredAt}pageInfo{hasNextPage endCursor}}}}"""
                try:
                    owner,repo=meta["full_name"].split("/",1)
                    diagnostic["graphql_count_comparison"]=transport.call("/graphql",query=query,variables={"owner":owner,"name":repo})["data"]["repository"]
                except DataError as error:
                    diagnostic["graphql_count_comparison"]={"error":str(error)}
                results["checks"]["reference_nonzero_stars"]["diagnostic"]=diagnostic
        else:
            results["checks"]["reference_nonzero_stars"]={"state":"not_tested","reason":"Reference repository currently has zero stars"}
    except (DataError,KeyError) as error:
        results["checks"]["reference_nonzero_stars"]={"state":"failed","reason":str(error) if isinstance(error,DataError) else "INVALID_REFERENCE_RESPONSE"}
    try:
        markdown=(ROOT/"README.md").read_text(encoding="utf-8")
        rendered=transport.call("/markdown",markdown=markdown,accept="text/html")
        write_text(ROOT/"previews/github-rendered-fragment.html",rendered)
        audit=MarkupAudit()
        audit.feed(rendered)
        expected=4+len(c["works"])
        links=all(w["url"] in audit.links_containing_images for w in c["works"])
        svgs=any(s.get("srcset","").endswith(".svg") for s in audit.sources)
        media=any("prefers-color-scheme: dark" in s.get("media","") for s in audit.sources)
        mobile=any("max-width" in s.get("media","") for s in audit.sources)
        results["checks"]["github_markdown"]={"state":"ok" if audit.pictures==expected and links and svgs and media and mobile else "failed",
                "pictures":audit.pictures,"sources":len(audit.sources),"images":len(audit.images),"independent_work_links":links,
                "work_image_ancestor_links":sorted(audit.links_containing_images),
                "native_svg_sources_retained":svgs,"dark_media_retained":media,"mobile_media_retained":mobile,
                "method":"GitHub official POST /markdown, GFM mode, stateless render; no repository created"}
        # Local replay preserves the real sanitized markup and standard README spacing.
        local=rendered.replace('src="assets/','src="../assets/').replace('srcset="assets/','srcset="../assets/')
        page='<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'
        page+='*{box-sizing:border-box}body{margin:0;background:#f6f5f2}main{max-width:840px;margin:auto;line-height:1.5}p{margin:0 0 16px}img{max-width:100%;height:auto;vertical-align:top}picture{display:inline}a{color:inherit}@media(prefers-color-scheme:dark){body{background:#0c0b08}}'
        page+='</style></head><body><main>'+local+'</main></body></html>'
        write_text(ROOT/"previews/github-rendered.html",page)
    except DataError as error:
        results["checks"]["github_markdown"]={"state":"failed","reason":str(error)}
    for name in ("languages","activity","community","stars"):
        value=read_json(ROOT/"assets/data"/(name+".json"),{})
        if name=="activity" and value.get("payload"):
            data=value["payload"]
            results["checks"]["activity_totals"]={"state":value["state"],"days":len(data["days"]),"weeks":len(data["weeks"]),"daily_total":sum(d["count"] for d in data["days"]),"weekly_total":sum(w["count"] for w in data["weeks"]),"reported_total":data["total"],"peak":data["peak"],"nonzero_days":[d for d in data["days"] if d["count"]>0],"window":[data["start"],data["end"]]}
        elif name=="languages":
            payload=value.get("payload") or {}
            results["checks"]["languages_bytes"]={"state":value.get("state"),"total_bytes":payload.get("total_bytes"),"by_language":payload.get("languages"),"by_repo":payload.get("repos")}
    results["requests"]=transport.observations
    results["real_published_profile_rendering"]="NOT TESTED: no remote repository changes authorized"
    write_json(ROOT/"reports/round2-real-validation.json",results)
    print(json.dumps({k:v.get("state") for k,v in results["checks"].items()},ensure_ascii=False))


if __name__=="__main__":
    main()
