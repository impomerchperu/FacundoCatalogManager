                try:
                    candidate_html, keys = future.result()
                except requests.RequestException:
                    continue
                if not candidate_html:
                    continue
                results.append((candidate, keys))
                if keys:
                    with self._category_html_cache_lock:
                        self._category_html_cache[candidate] = candidate_html
        candidate_order = {
            candidate: index for index, candidate in enumerate(candidates)
        }
        results.sort(key=lambda result: candidate_order[result[0]])
        return results

    def _fetch_product_keys(self, url: str) -> tuple[str, set[str]]:
        html = self.get_html(url)
        if not html:
            return "", set()