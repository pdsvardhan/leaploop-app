/* App shell + routing. Auth is enforced upstream by Authentik forward-auth, so the app renders
   directly; "Logout" hands off to the Authentik sign-out endpoint. */
import { useState, useEffect } from 'react';
import { Sidebar, Topbar, MobileTop, BottomNav, ErrorBoundary } from './components.jsx';
import { useRoles, useHealth } from './api.js';
import { HomeScreen } from './screens/Home.jsx';
import { TriageScreen } from './screens/Triage.jsx';
import { ApplyScreen } from './screens/Apply.jsx';
import { TrackerScreen } from './screens/Tracker.jsx';
import { GenerateScreen } from './screens/Generate.jsx';
import { SettingsScreen } from './screens/Settings.jsx';

function useMedia(maxw) {
  const [m, setM] = useState(() => window.matchMedia(`(max-width:${maxw}px)`).matches);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width:${maxw}px)`);
    const h = (e) => setM(e.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, [maxw]);
  return m;
}

export function App() {
  const [route, setRoute] = useState('home');
  const [query, setQuery] = useState('');
  const mobile = useMedia(560);

  const { data: triage } = useRoles('triage');
  const { data: health } = useHealth();
  const counts = {
    triage: triage?.counts?.triage || 0,
    apply: triage?.counts?.apply || 0,
    broken: health?.brokenFeeds || 0,
  };

  const go = (r) => {
    if (r === 'login') { window.location.href = '/outpost.goauthentik.io/sign_out'; return; }
    if (r !== 'triage' && r !== 'tracker') setQuery('');   // search only applies to those two screens
    setRoute(r);
    document.querySelector('.scroll')?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const screens = {
    home: <HomeScreen go={go} />,
    triage: <TriageScreen query={query} go={go} />,
    apply: <ApplyScreen />,
    tracker: <TrackerScreen query={query} />,
    generate: <GenerateScreen />,
    settings: <SettingsScreen />,
  };

  return (
    <div className="leap-root">
      {!mobile && <Sidebar route={route} go={go} counts={counts} />}
      <div className="main">
        {mobile ? <MobileTop /> : <Topbar onSearch={setQuery} query={query} showSearch={route === 'triage' || route === 'tracker'} />}
        <div className="scroll">
          <div key={route} className="screen-anim"><ErrorBoundary key={route}>{screens[route]}</ErrorBoundary></div>
        </div>
      </div>
      {mobile && <BottomNav route={route} go={go} counts={counts} />}
    </div>
  );
}
