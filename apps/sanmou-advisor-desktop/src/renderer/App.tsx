import { useEffect, useState } from "react";

import { getRuntimeConfig, healthCheck } from "./api";
import DaqiaoWorkspace, { DAQIAO_SCENES } from "./daqiao/DaqiaoWorkspace";
import LegacyAdvisorWorkbench, { EvidenceQualityPanel } from "./LegacyAdvisorWorkbench";

export { EvidenceQualityPanel };

function isExplicitDaqiaoLocation(): boolean {
  const rawHash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1).split("?")[0]
    : "";
  if (rawHash && (DAQIAO_SCENES as readonly string[]).includes(rawHash)) {
    return true;
  }
  return new URLSearchParams(window.location.search).get("ui") === "daqiao";
}

export default function App() {
  const [hash, setHash] = useState(() => window.location.hash);
  const [syntheticLegacyMode, setSyntheticLegacyMode] = useState(false);

  useEffect(() => {
    function onHashChange() {
      setHash(window.location.hash);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function probeLegacyEnvironment() {
      if (isExplicitDaqiaoLocation()) {
        return;
      }
      const config = await getRuntimeConfig().catch(() => null);
      if (cancelled) return;
      if (config?.apiLaunch?.status === "failed" || config?.apiLaunch?.status === "exited") {
        setSyntheticLegacyMode(true);
        return;
      }
      try {
        const health = await healthCheck();
        if (cancelled) return;
        if (health.data_dir === "synthetic-test") {
          setSyntheticLegacyMode(true);
        }
      } catch {
        const latest = await getRuntimeConfig().catch(() => null);
        if (cancelled) return;
        if (latest?.apiLaunch?.status === "failed" || latest?.apiLaunch?.status === "exited") {
          setSyntheticLegacyMode(true);
        }
      }
    }

    void probeLegacyEnvironment();
    const timer = window.setInterval(async () => {
      if (cancelled || isExplicitDaqiaoLocation()) return;
      const latest = await getRuntimeConfig().catch(() => null);
      if (cancelled || !latest?.apiLaunch) return;
      if (
        latest.apiLaunch.mode === "embedded" &&
        (latest.apiLaunch.status === "failed" || latest.apiLaunch.status === "exited")
      ) {
        setSyntheticLegacyMode(true);
      }
    }, 500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const showLegacyAdvisor =
    hash === "#advisor" || (syntheticLegacyMode && !isExplicitDaqiaoLocation());

  if (showLegacyAdvisor) {
    return <LegacyAdvisorWorkbench />;
  }

  return <DaqiaoWorkspace />;
}
