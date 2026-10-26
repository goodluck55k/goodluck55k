"""Round 2 regression tests: CLI transport, real vector output, scale and counts."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from common import ROOT,config,read_json
from collect import Client,DataError,contribution_data,star_data
from github_cli import GhTransport
from render import header,stats
from vector import monotone_curve
from validate_remote import MarkupAudit


class RoundTwoTests(unittest.TestCase):
    def test_gfm_empty_anchor_is_not_a_clickable_work(self):
        audit=MarkupAudit()
        audit.feed('<a href="https://github.com/tester/project"><picture></picture></a><img src="work.png">')
        self.assertNotIn("https://github.com/tester/project",audit.links_containing_images)
        audit=MarkupAudit()
        audit.feed('<p><a href="https://github.com/tester/project"><picture><img src="work.png"></picture></a></p>')
        self.assertIn("https://github.com/tester/project",audit.links_containing_images)
    def test_gh_transport_keeps_token_inside_cli(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,'HTTP/2.0 200 OK\nX-RateLimit-Remaining: 4998\n\n{"total_count":0}',""))
        transport=GhTransport("gh-fixture",runner)
        self.assertEqual(transport.call("/search/issues?q=is:public")["total_count"],0)
        args,body,exe=runner.call_args.args
        self.assertIn("GET",args)
        self.assertNotIn("Authorization",str(args))
        self.assertNotIn("auth token",str(args))
        self.assertEqual(transport.observations[0]["rate_remaining"],"4998")

    def test_gh_query_error_is_unknown_not_zero(self):
        payload={"data":None,"errors":[{"type":"INSUFFICIENT_SCOPES","message":"Field requires read permission","path":["user","contributionsCollection"]}]}
        runner=Mock(return_value=subprocess.CompletedProcess([],1,'HTTP/2.0 200 OK\n\n'+json.dumps(payload),""))
        transport=GhTransport("gh-fixture",runner)
        with self.assertRaisesRegex(DataError,"GRAPHQL_ERRORS"):
            transport.call("/graphql",query="query { user(login:\"tester\") { login } }")
        self.assertEqual(transport.observations[0]["graphql_errors"][0]["type"],"INSUFFICIENT_SCOPES")

    def test_gh_transport_refuses_mutations(self):
        runner=Mock()
        transport=GhTransport("gh-fixture",runner)
        with self.assertRaises(DataError):
            transport.call("/graphql",query="mutation { deleteRepository }")
        with self.assertRaises(DataError):
            transport.call("/repos/tester/example",query="query { viewer { login } }")
        runner.assert_not_called()

    def test_gh_http_error_classification(self):
        for status,headers,expected in [(401,"","HTTP_401"),(403,"","HTTP_403"),(403,"X-RateLimit-Remaining: 0\n","RATE_LIMIT")]:
            runner=Mock(return_value=subprocess.CompletedProcess([],1,f'HTTP/2.0 {status} Error\n{headers}\n{{"message":"failure"}}',""))
            with self.assertRaisesRegex(DataError,expected):
                GhTransport("gh-fixture",runner).call("/repos/tester/example/languages")

    def test_private_counts_are_not_mixed_into_public_calendar(self):
        collection={"restrictedContributionsCount":0,"commitContributionsByRepository":[{"repository":{"isPrivate":True}}]}
        client=Mock(token="managed-fixture")
        client.request.return_value={"data":{"user":{"contributionsCollection":collection}}}
        with self.assertRaisesRegex(DataError,"PRIVATE_CONTRIBUTIONS_EXCLUDED"):
            contribution_data(client,"tester","2026-01-01","2026-01-01")

    def test_star_rest_404_recovers_via_real_timestamp_graphql(self):
        client=Mock(token="managed-fixture")
        client.pages.side_effect=DataError("HTTP_404")
        client.request.return_value={"data":{"repository":{"isPrivate":False,"stargazers":{"edges":[{"starredAt":"2026-01-01T00:00:00Z"}],"pageInfo":{"hasNextPage":False,"endCursor":None}}}}}
        repository={"name":"example","full_name":"tester/example","created_at":"2025-01-01T00:00:00Z","stars":1,"fork":False}
        result=star_data(client,[repository])["series"][0]
        self.assertEqual(result["history_state"],"ok")
        self.assertEqual(result["starred_at"],["2026-01-01T00:00:00Z"])
        self.assertIn("GraphQL",result["source"])
        self.assertEqual(result["fallback_attempts"][0]["reason"],"HTTP_404")

    def test_curve_interpolates_real_points_without_overshoot(self):
        points=[(0,0),(7,0),(14,4),(21,0),(28,0),(35,2),(42,0)]
        path,samples=monotone_curve(points)
        self.assertIn("C",path)
        self.assertTrue(all(0<=y<=4 for _,y in samples))
        for point in points:
            self.assertIn(point,samples)

    def test_svg_is_native_and_self_contained(self):
        namespace={"s":"http://www.w3.org/2000/svg"}
        for path in (ROOT/"assets/stats").glob("*.svg"):
            xml=path.read_text(encoding="utf-8")
            root=ET.fromstring(xml)
            self.assertFalse(root.findall('.//s:image',namespace))
            self.assertFalse(root.findall('.//s:script',namespace))
            self.assertNotIn("data:image",xml)
            self.assertNotIn("@font-face",xml)
            self.assertGreater(len(root.findall('.//s:path',namespace)),100)
            titles=[e.text for e in root.findall('.//s:title',namespace)]
            for name in ("Languages","Activity","Community","Stars"):
                self.assertIn(name,titles)

    def test_dyna_final_scale_keeps_header_canvas_and_text_clear(self):
        c=config()
        for width in (420,840):
            p=header(c,c["themes"]["light"],width)
            box=p.images[0]["box"]
            expected=(122 if width==420 else 212)*1.2*.94
            self.assertAlmostEqual(box[3]-box[1],expected)
            self.assertEqual(p.h,204 if width==420 else 279)
            for text in p.bounds:
                x1,y1,x2,y2=text["box"]
                self.assertFalse(x1<box[2] and x2>box[0] and y1<box[3] and y2>box[1])

    def test_footer_transparent_art_is_restrained_and_clear_of_text(self):
        audit=read_json(ROOT/"previews/layout-audit.json")
        for p in audit:
            if "footer-" in p["file"]:
                record=p["images"][0]
                x1,y1,x2,y2=record["box"]
                self.assertAlmostEqual((x2-x1)/(y2-y1),453/494)
                self.assertGreater(x1,p["width"]*.65)
                self.assertLess(y2-y1,150 if p["width"]<600 else 200)
                self.assertLess(record["paper_blend"],.2)
                for text in p["text"]:
                    tx1,ty1,tx2,ty2=text["box"]
                    self.assertFalse(tx1<x2 and tx2>x1 and ty1<y2 and ty2>y1)


if __name__=="__main__":
    unittest.main()
