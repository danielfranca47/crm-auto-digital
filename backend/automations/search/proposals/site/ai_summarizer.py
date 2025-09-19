# modules/ai_summarizer.py
from typing import List, Dict, Tuple
from collections import defaultdict

class AISummarizer:
    def _index_issues(self, issues_rows: List[Dict]) -> Dict[str, Dict]:
        """
        Agrupa issues por website e produz contagens por severidade e categorias.
        Retorna: { website: {"critical":X,"major":Y,"minor":Z,"cats":{SEO:..,UX:..,...}} }
        """
        idx = {}
        for r in issues_rows or []:
            w = (r.get("website") or "").strip()
            if not w:
                continue
            if w not in idx:
                idx[w] = {"critical": 0, "major": 0, "minor": 0, "cats": defaultdict(int)}
            sev = (r.get("severity") or "").strip().lower()
            cat = (r.get("category") or "").strip()
            if sev in ("critical", "critico"):
                idx[w]["critical"] += 1
            elif sev == "major":
                idx[w]["major"] += 1
            else:
                idx[w]["minor"] += 1
            if cat:
                idx[w]["cats"][cat] += 1
        # normaliza cats para dict comum
        for w in list(idx.keys()):
            idx[w]["cats"] = dict(idx[w]["cats"])
        return idx

    def _no_website(self, item: Dict) -> bool:
        site = (item.get("website") or item.get("website_canonical") or "").strip()
        if not site:
            return True
        if item.get("own_domain") is False or item.get("no_own_site") is True:
            return True
        return int(item.get("pages_crawled") or 0) == 0

    def _opportunity_score(self, item: Dict, agg: Dict) -> int:
        """
        Quanto maior, mais 'oportunidade de melhoria' comercial.
        Considera: severidades, mobile/SSL, ausência de site.
        """
        score = 0
        if self._no_website(item):
            score += 8
        score += (agg.get("critical", 0) * 4) + (agg.get("major", 0) * 2) + (agg.get("minor", 0) * 1)
        if not item.get("mobile_ready"):
            score += 3
        if not item.get("ssl_ok"):
            score += 3
        return score

    def _priority(self, trust: int, opp: int) -> str:
        """
        A: alta confiança + muitos problemas (grande potencial comercial)
        B: média confiança e/ou moderados problemas
        C: baixa confiança e/ou poucas alavancas
        """
        if trust >= 80 and opp >= 5:
            return "A"
        if trust >= 60 and opp >= 3:
            return "B"
        return "C"

    def _next_action(self, item: Dict, agg: Dict) -> str:
        # Para casos sem site próprio (ou sociais/whatsapp/etc)
        if self._no_website(item):
            kind = (item.get("website_kind") or "").strip()
            if kind in {"social", "messaging", "directory", "link_aggregator", "builder_hosted"}:
                return "Propor criação de site próprio (domínio customizado) com páginas essenciais e CTA/WhatsApp."
            return "Propor criação de site one-page responsivo com WhatsApp e CTA."
        # Outros casos: opcionalmente poderíamos sugerir melhorias com base nas issues
        crit, maj = agg.get("critical", 0), agg.get("major", 0)
        if crit > 0:
            return "Agendar call para correções críticas (SEO/Tech) e priorização."
        if maj > 0:
            return "Sugerir pacote de melhorias (SEO on-page, performance e UX)."
        return "Manter monitoramento e otimizações leves."

    def _insights(self, item: Dict, agg: Dict, prio: str, trust_adj: int) -> str:
        name = (item.get("name", "") or "").strip()
        ssl_ok = bool(item.get("ssl_ok"))
        mob = bool(item.get("mobile_ready"))
        crit, maj, minor = agg.get("critical", 0), agg.get("major", 0), agg.get("minor", 0)

        flags = []
        if not ssl_ok: flags.append("sem HTTPS")
        if not mob: flags.append("sem mobile")
        if crit or maj or minor:
            flags.append(f"issues: {crit}C/{maj}M/{minor}m")

        # destacar tipo de “site” quando não é domínio próprio
        if item.get("no_own_site") is True or item.get("own_domain") is False:
            kind = item.get("website_kind") or "desconhecido"
            flags.insert(0, f"sem site próprio (kind: {kind})")

        flag_txt = "; ".join(flags) if flags else "s/ issues relevantes"
        return f"{name} — prioridade {prio}. Trust {trust_adj}. Sinais do site: {flag_txt}."

    def summarize(self, items: List[Dict], issues_rows: List[Dict] | None = None) -> List[Dict]:
        idx = self._index_issues(issues_rows or [])
        out = []
        for it in items:
            w = (it.get("website") or it.get("website_canonical") or "").strip()
            agg = idx.get(w, {"critical":0,"major":0,"minor":0,"cats":{}})

            trust_orig = int(it.get("trust_score") or 0)
            trust_adj = trust_orig

            # Penalidade para ranking quando não tem site próprio
            if it.get("no_own_site") is True:
                trust_adj = max(0, trust_orig - 15)

            opp = self._opportunity_score(it, agg)

            # Prioridade: override A quando não há site próprio
            if it.get("no_own_site") is True:
                prio = "A"
            else:
                prio = self._priority(trust_adj, opp)

            action = self._next_action(it, agg)
            insight = self._insights(it, agg, prio, trust_adj)

            out.append({
                **it,
                "priority": prio,
                "next_action": action,
                "insights": insight,
                "trust_score_adj": trust_adj,   # mantém original e expõe o ajustado
                "issues_critical": agg.get("critical", 0),
                "issues_major": agg.get("major", 0),
                "issues_minor": agg.get("minor", 0),
            })
        return out
