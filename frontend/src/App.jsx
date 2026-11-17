import { useCallback, useEffect, useState } from "react";

const PORTALS = {
  CITIZEN: { label: "নাগরিক", icon: "01", description: "নাগরিক সহায়তা ও নিরাপদ যাতায়াত" },
  POLICE: { label: "ট্রাফিক পুলিশ", icon: "02", description: "রিপোর্ট যাচাই ও পর্যালোচনা" },
  DRIVER: { label: "বাস চালক", icon: "03", description: "চালক প্রশিক্ষণ ও নিরাপত্তা" },
};

const ISSUE_TYPES = [
  ["OVERCROWDING", "অতিরিক্ত যাত্রী"],
  ["FEMALE_SEAT_VIOLATION", "নারী আসন সংক্রান্ত সমস্যা"],
  ["FARE_BARGAINING", "ভাড়া নিয়ে সমস্যা"],
  ["RASH_DRIVING", "বেপরোয়া গাড়ি চালানো"],
];

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const body = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof body.detail === "string" ? body.detail : "অনুরোধটি সম্পন্ন করা যায়নি।",
    );
    error.status = response.status;
    throw error;
  }
  return body;
}

function useNotice() {
  const [notice, setNotice] = useState(null);
  const notify = useCallback((message, isError = false) => {
    setNotice({ message, isError });
    window.clearTimeout(notify.timeout);
    notify.timeout = window.setTimeout(() => setNotice(null), 5000);
  }, []);
  return [notice, notify];
}

function App() {
  return window.location.pathname === "/admin" ? <AdminApp /> : <CitizenApp />;
}

function CitizenApp() {
  const [user, setUser] = useState(null);
  const [portal, setPortal] = useState("CITIZEN");
  const [authMode, setAuthMode] = useState("login");
  const [loading, setLoading] = useState(true);
  const [notice, notify] = useNotice();

  useEffect(() => {
    let active = true;
    api("/api/v1/auth/session")
      .then(({ user: account }) => {
        if (active && account) {
          setUser(account);
          setPortal(account.user_role);
        }
      })
      .catch((error) => {
        if (active && error.status !== 401) notify(error.message, true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [notify]);

  async function signOut() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch (error) {
      notify(error.message, true);
    } finally {
      setUser(null);
      setPortal("CITIZEN");
      setAuthMode("login");
    }
  }

  if (loading) {
    return <main className="loading-screen"><span className="loader" />SmartTransit খুলছে…</main>;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="SmartTransit home">
          <span className="brand-mark">ST</span>
          <span><strong>SMART<span>TRANSIT</span></strong><small>নিরাপদ শহর, সচেতন যাত্রা</small></span>
        </a>
        <div className="topbar-actions">
          <span className="security-label"><i /> ব্যক্তিগত ও সুরক্ষিত</span>
          {user ? (
            <>
              <span className="user-chip"><b>{user.full_name?.slice(0, 1)}</b>{user.full_name}</span>
              <button className="button button-quiet" onClick={signOut}>লগ আউট</button>
            </>
          ) : (
            <a className="button button-quiet" href="#login">অ্যাকাউন্টে প্রবেশ</a>
          )}
        </div>
      </header>

      <main>
        {!user ? (
          <Landing
            portal={portal}
            setPortal={setPortal}
            authMode={authMode}
            setAuthMode={setAuthMode}
            onSignedIn={(account) => {
              setUser(account);
              setPortal(account.user_role);
            }}
            notify={notify}
          />
        ) : (
          <PortalHome user={user} notify={notify} />
        )}
      </main>

      <footer className="footer">
        <span>SMARTTRANSIT · নাগরিক নিরাপত্তা সহায়তা</span>
        <span>জরুরি বিপদে <a href="tel:999">৯৯৯</a>-এ কল করুন · <a href="/admin">প্রশাসক প্রবেশ</a></span>
      </footer>
      {notice && (
        <div className={`notice ${notice.isError ? "notice-error" : ""}`} role="status">
          {notice.message}
        </div>
      )}
    </div>
  );
}

function AdminApp() {
  const [adminEmail, setAdminEmail] = useState(null);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [createdAccounts, setCreatedAccounts] = useState([]);
  const [notice, notify] = useNotice();

  useEffect(() => {
    let active = true;
    api("/api/v1/admin/session")
      .then((result) => {
        if (active) {
          setConfigured(result.configured);
          setAdminEmail(result.admin_email);
        }
      })
      .catch((error) => {
        if (active) notify(error.message, true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [notify]);

  async function signIn(event) {
    event.preventDefault();
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api("/api/v1/admin/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setAdminEmail(result.admin_email);
      notify("Admin পোর্টালে প্রবেশ হয়েছে।");
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try {
      await api("/api/v1/admin/logout", { method: "POST" });
    } catch (error) {
      notify(error.message, true);
    } finally {
      setAdminEmail(null);
      setCreatedAccounts([]);
    }
  }

  async function createStaffAccount(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    if (values.password !== values.confirm_password) {
      notify("দুইবার দেওয়া password এক নয়।", true);
      return;
    }
    delete values.confirm_password;
    setBusy(true);
    try {
      const result = await api("/api/v1/admin/staff", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setCreatedAccounts((accounts) => [result.user, ...accounts]);
      form.reset();
      notify(`${result.user.user_role} account তৈরি হয়েছে।`);
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="loading-screen"><span className="loader" />Admin portal খুলছে…</main>;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="SmartTransit home">
          <span className="brand-mark">ST</span>
          <span><strong>SMART<span>TRANSIT</span></strong><small>Admin portal</small></span>
        </a>
        {adminEmail && (
          <div className="topbar-actions">
            <span className="user-chip">{adminEmail}</span>
            <button className="button button-quiet" onClick={signOut}>লগ আউট</button>
          </div>
        )}
      </header>

      <main className="admin-main">
        {!configured ? (
          <section className="auth-card admin-card">
            <div className="section-kicker">ADMIN / SETUP REQUIRED</div>
            <h2>Admin login সেটআপ করুন</h2>
            <p className="muted">প্রথমে server বন্ধ করে project folder-এ নিচের command চালান। Password গোপন prompt-এ দিতে হবে, chat বা code-এ নয়।</p>
            <pre className="admin-command">.\.venv\Scripts\python.exe configure_admin.py</pre>
            <a className="button button-outline" href="/">মূল পোর্টালে ফিরুন</a>
          </section>
        ) : !adminEmail ? (
          <section className="auth-card admin-card">
            <div className="section-kicker">SECURE ACCESS / ADMIN</div>
            <h1>প্রশাসক প্রবেশ</h1>
            <p className="muted">এই পোর্টাল থেকে অনুমোদিত Traffic Police ও Bus Driver account তৈরি করুন।</p>
            <form className="form-stack" onSubmit={signIn}>
              <label>Admin email
                <input name="email" type="email" required maxLength="255" autoComplete="username" placeholder="admin@example.com" />
              </label>
              <label>Password
                <input name="password" type="password" required maxLength="128" autoComplete="current-password" />
              </label>
              <button className="button button-primary full-button" disabled={busy}>
                {busy ? "যাচাই হচ্ছে…" : "Admin হিসেবে প্রবেশ"}<span>→</span>
              </button>
            </form>
            <div className="privacy-note"><span>🔒</span> Admin password server-এ hash আকারে রাখা হয়।</div>
          </section>
        ) : (
          <div className="admin-dashboard">
            <section className="dashboard-heading">
              <div>
                <div className="section-kicker">STAFF ACCOUNTS / ADMIN ONLY</div>
                <h1>Police ও Driver account</h1>
                <p>কর্মীর পরিচয় যাচাই করে আলাদা password দিয়ে account তৈরি করুন।</p>
              </div>
            </section>
            <div className="admin-content-grid">
              <section className="panel">
                <div className="section-kicker">NEW STAFF ACCOUNT</div>
                <h2>নতুন account তৈরি</h2>
                <form className="form-stack admin-form" onSubmit={createStaffAccount}>
                  <label>Portal role
                    <select name="user_role" required defaultValue="POLICE">
                      <option value="POLICE">Traffic Police</option>
                      <option value="DRIVER">Bus Driver</option>
                    </select>
                  </label>
                  <label>পুরো নাম
                    <input name="full_name" required minLength="2" maxLength="150" autoComplete="name" />
                  </label>
                  <label>কাজের email
                    <input name="email" type="email" required maxLength="255" autoComplete="email" />
                  </label>
                  <label>ফোন নম্বর
                    <input name="phone" type="tel" required minLength="7" maxLength="30" autoComplete="tel" />
                  </label>
                  <label>প্রাথমিক password <span className="field-hint">কমপক্ষে ১০ অক্ষর; কর্মীকে নিরাপদে জানান</span>
                    <input name="password" type="password" required minLength="10" maxLength="128" autoComplete="new-password" />
                  </label>
                  <label>Password নিশ্চিত করুন
                    <input name="confirm_password" type="password" required minLength="10" maxLength="128" autoComplete="new-password" />
                  </label>
                  <button className="button button-primary full-button" disabled={busy}>
                    {busy ? "তৈরি হচ্ছে…" : "Staff account তৈরি করুন"}<span>→</span>
                  </button>
                </form>
              </section>
              <section className="panel admin-created-panel">
                <div className="panel-heading">
                  <div><div className="section-kicker">THIS SESSION</div><h2>তৈরি করা account</h2></div>
                  <span className="count-badge">{createdAccounts.length}</span>
                </div>
                {createdAccounts.length ? (
                  <ul className="report-list">
                    {createdAccounts.map((account) => (
                      <li key={account.id}>
                        <span className="status-mark status-verified" />
                        <div><strong>{account.full_name} · {account.user_role}</strong><small>{account.email} · {account.phone}</small></div>
                      </li>
                    ))}
                  </ul>
                ) : <div className="empty-state"><span>+</span><p>এই session-এ তৈরি account এখানে দেখাবে।</p></div>}
                <p className="form-footnote">Account-এর password এই তালিকায় সংরক্ষণ বা প্রদর্শন করা হয় না।</p>
              </section>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <span>SMARTTRANSIT · Admin portal</span>
        <a href="/">মূল পোর্টালে ফিরুন</a>
      </footer>
      {notice && (
        <div className={`notice ${notice.isError ? "notice-error" : ""}`} role="status">
          {notice.message}
        </div>
      )}
    </div>
  );
}

function Landing({ portal, setPortal, authMode, setAuthMode, onSignedIn, notify }) {
  return (
    <div className="landing-grid">
      <section className="welcome-panel">
        <div className="eyebrow"><span className="pulse-dot" /> DHAKA · CIVIC MOBILITY</div>
        <h1>যাত্রাপথে<br /><em>নিরাপত্তা</em> আপনার অধিকার।</h1>
        <p className="welcome-copy">
          জরুরি সহায়তা, যাচাইকৃত থানার তথ্য এবং যাতায়াতের সমস্যা জানানোর জন্য
          আপনার নিজস্ব সুরক্ষিত পোর্টাল।
        </p>
        <a className="emergency-card" href="tel:999">
          <span className="emergency-icon">!</span>
          <span><small>বাংলাদেশের জাতীয় জরুরি সেবা</small><strong>৯৯৯-এ কল করুন</strong></span>
          <span className="arrow">↗</span>
        </a>
        <div className="welcome-foot">
          <span><b>01</b> পোর্টাল নির্বাচন</span><span><b>02</b> নিরাপদে প্রবেশ</span><span><b>03</b> সহায়তা নিন</span>
        </div>
      </section>

      <section className="auth-card" id="login">
        <div className="section-kicker">SECURE ACCESS / 01</div>
        <h2>{authMode === "login" ? "আপনার পোর্টালে প্রবেশ" : "নাগরিক অ্যাকাউন্ট তৈরি"}</h2>
        <p className="muted">আপনার অ্যাকাউন্টের তথ্য ও সহায়তা আলাদা করে সুরক্ষিত রাখা হয়।</p>

        <div className="portal-selector" role="tablist" aria-label="পোর্টাল নির্বাচন">
          {Object.entries(PORTALS).map(([key, item]) => (
            <button
              key={key}
              role="tab"
              aria-selected={portal === key}
              className={portal === key ? "portal-option selected" : "portal-option"}
              onClick={() => {
                setPortal(key);
                if (key !== "CITIZEN") setAuthMode("login");
              }}
            >
              <small>{item.icon}</small>{item.label}
            </button>
          ))}
        </div>
        <div className="selected-portal-note"><span className="mini-shield">✓</span>{PORTALS[portal].description}</div>

        {authMode === "login" ? (
          <LoginForm portal={portal} onSignedIn={onSignedIn} notify={notify} />
        ) : (
          <RegisterForm onSignedIn={onSignedIn} notify={notify} />
        )}
        <div className="auth-switch">
          {portal === "CITIZEN" && (
            authMode === "login" ? (
              <>নতুন নাগরিক? <button onClick={() => setAuthMode("register")}>অ্যাকাউন্ট খুলুন</button></>
            ) : (
              <>আগে থেকেই অ্যাকাউন্ট আছে? <button onClick={() => setAuthMode("login")}>প্রবেশ করুন</button></>
            )
          )}
        </div>
        <div className="privacy-note"><span>🔒</span> Police ও Driver অ্যাকাউন্ট শুধুমাত্র অনুমোদিত প্রশাসক তৈরি করেন।</div>
      </section>
    </div>
  );
}

function LoginForm({ portal, onSignedIn, notify }) {
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      if (result.user.user_role !== portal) {
        await api("/api/v1/auth/logout", { method: "POST" });
        throw new Error(`এই অ্যাকাউন্টটি ${PORTALS[result.user.user_role]?.label || "অন্য"} পোর্টালের।`);
      }
      onSignedIn(result.user);
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={submit}>
      <label>ইমেইল
        <input name="email" type="email" autoComplete="username" required maxLength="255" placeholder="name@example.com" />
      </label>
      <label>পাসওয়ার্ড
        <input name="password" type="password" autoComplete="current-password" required maxLength="128" placeholder="আপনার পাসওয়ার্ড" />
      </label>
      <button className="button button-primary full-button" disabled={busy}>
        {busy ? "যাচাই হচ্ছে…" : `${PORTALS[portal].label} পোর্টালে প্রবেশ`}
        <span>→</span>
      </button>
    </form>
  );
}

function RegisterForm({ onSignedIn, notify }) {
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(values),
      });
      onSignedIn(result.user);
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={submit}>
      <label>পুরো নাম
        <input name="full_name" required minLength="2" maxLength="150" autoComplete="name" placeholder="আপনার নাম" />
      </label>
      <label>ইমেইল
        <input name="email" type="email" required maxLength="255" autoComplete="email" placeholder="name@example.com" />
      </label>
      <label>মোবাইল নম্বর
        <input name="phone" type="tel" required minLength="7" maxLength="30" autoComplete="tel" placeholder="+8801XXXXXXXXX" />
      </label>
      <label>পাসওয়ার্ড <span className="field-hint">কমপক্ষে ১০ অক্ষর</span>
        <input name="password" type="password" required minLength="10" maxLength="128" autoComplete="new-password" placeholder="শক্তিশালী পাসওয়ার্ড দিন" />
      </label>
      <button className="button button-primary full-button" disabled={busy}>
        {busy ? "অ্যাকাউন্ট তৈরি হচ্ছে…" : "নাগরিক অ্যাকাউন্ট তৈরি"}<span>→</span>
      </button>
      <p className="form-footnote">নিবন্ধনে NID বা পাসপোর্ট নম্বর চাওয়া হয় না।</p>
    </form>
  );
}

function PortalHome({ user, notify }) {
  const portal = PORTALS[user.user_role] || PORTALS.CITIZEN;
  return (
    <div className="dashboard">
      <section className="dashboard-heading">
        <div>
          <div className="section-kicker">SMARTTRANSIT / {user.user_role}</div>
          <h1>স্বাগতম, {user.full_name?.split(" ")[0]}।</h1>
          <p>{portal.description} — আপনার তথ্য আপনার অ্যাকাউন্টেই সীমাবদ্ধ।</p>
        </div>
        <div className="level-card"><small>আপনার পয়েন্ট</small><strong>{user.total_points || 0}</strong><span>LEVEL {user.current_level || 1}</span></div>
      </section>

      {user.user_role === "CITIZEN" && <CitizenPortal user={user} notify={notify} />}
      {user.user_role === "POLICE" && <PolicePortal user={user} notify={notify} />}
      {user.user_role === "DRIVER" && <DriverPortal user={user} notify={notify} />}

      <ChatBox role={user.user_role} notify={notify} />
    </div>
  );
}

function CitizenPortal({ user, notify }) {
  const [reports, setReports] = useState([]);
  const [busy, setBusy] = useState(false);
  const [location, setLocation] = useState(null);

  const loadReports = useCallback(async () => {
    try {
      const result = await api("/api/v1/observations?limit=20");
      setReports(result.observations);
    } catch (error) {
      if (error.status !== 401) notify(error.message, true);
    }
  }, [notify]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  function getLocation() {
    if (!navigator.geolocation) {
      notify("এই ব্রাউজারে অবস্থান-সুবিধা নেই।", true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setLocation({
        latitude: coords.latitude,
        longitude: coords.longitude,
      }),
      () => notify("অবস্থান পাওয়া যায়নি। ব্রাউজারের permission দিন অথবা পরে চেষ্টা করুন।", true),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  async function submitReport(event) {
    event.preventDefault();
    if (!location) {
      notify("রিপোর্ট পাঠাতে আগে অবস্থান নির্বাচন করুন।", true);
      return;
    }
    setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = {
      ...values,
      reporter_id: user.id,
      ...location,
    };
    payload.latitude = Number(payload.latitude);
    payload.longitude = Number(payload.longitude);
    if (!payload.image_url) delete payload.image_url;
    try {
      await api("/api/v1/observations", { method: "POST", body: JSON.stringify(payload) });
      notify("রিপোর্ট জমা হয়েছে। Police portal-এ যাচাইয়ের পর অবস্থা দেখা যাবে।");
      event.currentTarget.reset();
      setLocation(null);
      await loadReports();
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="emergency-strip">
        <div className="emergency-icon">!</div>
        <div><small>তাৎক্ষণিক বিপদ?</small><strong>চ্যাটের উত্তরের অপেক্ষা করবেন না — ৯৯৯-এ কল করুন।</strong></div>
        <a href="tel:999" className="button emergency-button">এখনই কল <span>↗</span></a>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">CITIZEN / 01</div><h2>যাতায়াত সমস্যা জানান</h2></div><span className="panel-number">+20 XP</span></div>
          <p className="muted">বাসে ঘটে যাওয়া সমস্যার রিপোর্ট দিন। আপনার রিপোর্ট অন্য নাগরিকের কাছে দেখানো হবে না।</p>
          <form className="form-stack report-form" onSubmit={submitReport}>
            <label>বাস নম্বর<input name="bus_number" required maxLength="50" placeholder="যেমন: ঢাকা মেট্রো-ব ১১-১২৩৪" /></label>
            <label>রুট<input name="route_name" required maxLength="150" placeholder="যেমন: মিরপুর ১ — ফার্মগেট" /></label>
            <label>সমস্যার ধরন
              <select name="issue_type" required>{ISSUE_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
            </label>
            <label>ছবির লিংক <span className="field-hint">ঐচ্ছিক — বাহ্যিক সাইটে ছবি দেবেন না যদি প্রাইভেসি গুরুত্বপূর্ণ হয়</span>
              <input name="image_url" type="url" maxLength="2048" placeholder="https://…" />
            </label>
            <div className="location-row">
              <div><strong>রিপোর্টের অবস্থান</strong><small>{location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : "আপনি চাইলে শুধু রিপোর্টের জন্য অবস্থান শেয়ার করুন"}</small></div>
              <button className="button button-outline" type="button" onClick={getLocation}>{location ? "অবস্থান নেওয়া হয়েছে" : "অবস্থান দিন"}</button>
            </div>
            <button className="button button-primary full-button" disabled={busy}>
              {busy ? "জমা হচ্ছে…" : "নিরাপদে রিপোর্ট জমা দিন"}<span>→</span>
            </button>
          </form>
        </section>

        <section className="panel report-list-panel">
          <div className="panel-heading"><div><div className="section-kicker">PRIVATE / YOUR REPORTS</div><h2>আপনার রিপোর্ট</h2></div><span className="count-badge">{reports.length}</span></div>
          {reports.length ? (
            <ul className="report-list">
              {reports.map((report) => (
                <li key={report.id}>
                  <span className={`status-mark status-${report.status?.toLowerCase()}`} />
                  <div><strong>{ISSUE_TYPES.find(([value]) => value === report.issue_type)?.[1] || report.issue_type}</strong><small>{report.bus_number} · {report.route_name}</small></div>
                  <span className="status-text">{report.status === "PENDING" ? "যাচাই চলছে" : report.status}</span>
                </li>
              ))}
            </ul>
          ) : <div className="empty-state"><span>↗</span><p>আপনার জমা দেওয়া রিপোর্ট এখানে দেখা যাবে।</p></div>}
        </section>
      </div>
    </>
  );
}

function PolicePortal({ user, notify }) {
  const [reports, setReports] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const loadQueue = useCallback(async () => {
    try {
      const result = await api(`/api/v1/police/observations?user_id=${encodeURIComponent(user.id)}`);
      setReports(result.observations);
    } catch (error) {
      notify(error.message, true);
    }
  }, [user.id, notify]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  async function review(report, decision) {
    setBusyId(report.id);
    try {
      await api(`/api/v1/police/observations/${report.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          reviewer_id: user.id,
          decision,
          review_note: "",
          fine_amount_bdt: 0,
        }),
      });
      notify("রিপোর্টের পর্যালোচনা সংরক্ষিত হয়েছে।");
      await loadQueue();
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading"><div><div className="section-kicker">POLICE / REVIEW QUEUE</div><h2>যাচাইয়ের অপেক্ষায়</h2></div><button className="button button-outline" onClick={loadQueue}>রিফ্রেশ ↻</button></div>
      {reports.length ? (
        <div className="staff-list">
          {reports.map((report) => (
            <article className="staff-report" key={report.id}>
              <div className="staff-report-main">
                <span className="case-label">CASE / {String(report.id).slice(0, 8).toUpperCase()}</span>
                <h3>{ISSUE_TYPES.find(([value]) => value === report.issue_type)?.[1] || report.issue_type}</h3>
                <p>{report.bus_number} · {report.route_name} · রিপোর্ট করেছেন {report.reporter_name}</p>
                <small>অবস্থান: {Number(report.latitude).toFixed(5)}, {Number(report.longitude).toFixed(5)}</small>
              </div>
              <div className="review-actions">
                <button className="button button-approve" disabled={busyId === report.id} onClick={() => review(report, "VERIFIED")}>যাচাই হয়েছে</button>
                <button className="button button-reject" disabled={busyId === report.id} onClick={() => review(report, "REJECTED")}>প্রত্যাখ্যান</button>
              </div>
            </article>
          ))}
        </div>
      ) : <div className="empty-state"><span>✓</span><p>এখন কোনো pending রিপোর্ট নেই।</p></div>}
    </section>
  );
}

function DriverPortal({ user, notify }) {
  const [routes, setRoutes] = useState([]);
  const [activeTripId, setActiveTripId] = useState(null);
  const [routeName, setRouteName] = useState("");
  const [busNumber, setBusNumber] = useState("");
  const [checkpoint, setCheckpoint] = useState(0);
  const [actions, setActions] = useState({ safe_actions: 0, hard_brakes: 0, speeding_events: 0 });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api("/api/v1/driver/routes")
      .then(({ routes: available }) => {
        setRoutes(available);
        setRouteName(available[0]?.route_name || "");
      })
      .catch((error) => notify(error.message, true));
  }, [notify]);

  async function startTrip(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const trip = await api("/api/v1/driver/trips", {
        method: "POST",
        body: JSON.stringify({ user_id: user.id, route_name: routeName, bus_number: busNumber }),
      });
      setActiveTripId(trip.trip_id);
      setCheckpoint(0);
      setActions({ safe_actions: 0, hard_brakes: 0, speeding_events: 0 });
      setResult(null);
      notify("নিরাপত্তা প্রশিক্ষণের যাত্রা শুরু হয়েছে।");
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  function chooseAction(key) {
    setActions((current) => ({ ...current, [key]: current[key] + 1 }));
    setCheckpoint((current) => current + 1);
  }

  async function finishTrip() {
    setBusy(true);
    try {
      const tripResult = await api(`/api/v1/driver/trips/${activeTripId}/complete`, {
        method: "POST",
        body: JSON.stringify({ user_id: user.id, ...actions }),
      });
      setResult(tripResult);
      setActiveTripId(null);
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel driver-panel">
      <div className="panel-heading"><div><div className="section-kicker">DRIVER / SAFE JOURNEY</div><h2>চালক নিরাপত্তা প্রশিক্ষণ</h2></div><span className="route-icon">↗</span></div>
      {!activeTripId ? (
        <form className="form-stack driver-form" onSubmit={startTrip}>
          <p className="muted">ঢাকার একটি রুটে তিনটি পরিস্থিতির অনুশীলন করুন। বাস্তব যাত্রার তথ্য এখানে ট্র্যাক করা হয় না।</p>
          <label>বাস নম্বর<input value={busNumber} onChange={(event) => setBusNumber(event.target.value)} required maxLength="50" placeholder="ঢাকা মেট্রো-ব ১১-১২৩৪" /></label>
          <label>রুট<select value={routeName} onChange={(event) => setRouteName(event.target.value)} required>{routes.map((route) => <option key={route.route_name}>{route.route_name}</option>)}</select></label>
          <button className="button button-primary" disabled={busy || !routes.length}>প্রশিক্ষণ শুরু করুন →</button>
          {result && <p className="success-note">যাত্রা শেষ · নিরাপত্তা স্কোর {result.safety_score}/100 · রেটিং {result.trip_rating}★</p>}
        </form>
      ) : (
        <div className="checkpoint">
          <small>পরিস্থিতি {checkpoint + 1} / 3</small>
          <h3>{[
            "একজন পথচারী ব্যস্ত বাসস্টপের কাছে।",
            "ফার্মগেটে যানজট বাড়ছে।",
            "আপনি একটি জনাকীর্ণ মোড়ের কাছে।",
          ][checkpoint] || "সব পরিস্থিতি শেষ। আপনার ফলাফল দেখুন।"}</h3>
          <div className="checkpoint-actions">
            <button className="button button-approve" disabled={checkpoint >= 3} onClick={() => chooseAction("safe_actions")}>নিরাপদে চালান</button>
            <button className="button button-outline" disabled={checkpoint >= 3} onClick={() => chooseAction("hard_brakes")}>হঠাৎ ব্রেক</button>
            <button className="button button-reject" disabled={checkpoint >= 3} onClick={() => chooseAction("speeding_events")}>গতি বাড়ান</button>
          </div>
          {checkpoint >= 3 && <button className="button button-primary" disabled={busy} onClick={finishTrip}>ফলাফল দেখুন →</button>}
        </div>
      )}
    </section>
  );
}

function ChatBox({ role, notify }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [stations, setStations] = useState([]);
  const [showHotlines, setShowHotlines] = useState(false);
  const [hotlines, setHotlines] = useState([]);
  const [hotlinesLoaded, setHotlinesLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    api("/api/v1/chat/history")
      .then((result) => {
        if (active) setMessages(result.messages);
      })
      .catch((error) => {
        if (active) notify(error.message, true);
      });
    return () => {
      active = false;
    };
  }, [role, notify]);

  useEffect(() => {
    if (role !== "CITIZEN" || !showHotlines || hotlinesLoaded) return undefined;
    let active = true;
    api("/api/v1/emergency/contacts")
      .then(({ contacts }) => {
        if (active) {
          setHotlines(contacts);
          setHotlinesLoaded(true);
        }
      })
      .catch((error) => {
        if (active) notify(error.message, true);
      });
    return () => {
      active = false;
    };
  }, [role, showHotlines, hotlinesLoaded, notify]);

  async function send(text, location = null) {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    setMessages((current) => [...current, { id: `pending-${Date.now()}`, role: "USER", content }]);
    setDraft("");
    try {
      const response = await api("/api/v1/chat/messages", {
        method: "POST",
        body: JSON.stringify({ message: content, ...(location || {}) }),
      });
      setMessages((current) => [...current, { id: `answer-${Date.now()}`, role: "ASSISTANT", content: response.reply }]);
      setStations(response.nearby_stations || []);
    } catch (error) {
      setMessages((current) => current.filter((message) => !String(message.id).startsWith("pending-")));
      setDraft(content);
      notify(error.message, true);
    } finally {
      setSending(false);
    }
  }

  function askNearby() {
    if (!navigator.geolocation) {
      notify("এই ব্রাউজারে অবস্থান-সুবিধা নেই।", true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => send("আমার নিকটস্থ থানা কোথায়?", {
        latitude: coords.latitude,
        longitude: coords.longitude,
      }),
      () => notify("অবস্থান শেয়ার করা যায়নি। permission দিন অথবা পরে চেষ্টা করুন।", true),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  }

  function submit(event) {
    event.preventDefault();
    send(draft);
  }

  const suggestions = role === "CITIZEN"
    ? [
      "জরুরি অবস্থায় কী করব?",
      "আমার মোবাইল ফোন চুরি হয়েছে। কী করব?",
      "অনলাইনে ব্ল্যাকমেইল করলে কী করব?",
      "থানায় অনলাইনে জিডি করতে পারব?",
      "আগুন লাগলে কী করব?",
    ]
    : role === "POLICE"
      ? ["রিপোর্ট যাচাইয়ের সময় কী খেয়াল রাখব?", "জরুরি পরিস্থিতিতে কী করব?"]
      : ["দুর্ঘটনা হলে কী করব?", "নিরাপদে বাস চালানোর পরামর্শ দিন।"];

  return (
    <section className="panel chat-panel" id="help-chat">
      <div className="panel-heading">
        <div><div className="section-kicker">PRIVATE ASSISTANT / {role}</div><h2>সুরক্ষা সহায়তা চ্যাট</h2></div>
        <span className="ai-badge"><i /> LOCAL AI</span>
      </div>
      <div className="chat-privacy">
        <span>🔐</span>
        <p>চ্যাট আপনার এই পোর্টাল ও অ্যাকাউন্টেই সীমিত; ডেটাবেসে এনক্রিপ্ট করে রাখা হয়। AI উত্তর স্থানীয় জরুরি-তথ্য থেকে আসে — বাইরের AI-কে আপনার প্রশ্ন পাঠানো হয় না।</p>
      </div>
      <div className="chat-transcript" aria-live="polite">
        {messages.length === 0 && (
          <div className="assistant-message">
            <span className="assistant-avatar">AI</span>
            <p>আমি জরুরি যোগাযোগ, থানায় অভিযোগ জানানোর সাধারণ ধাপ এবং যাতায়াত-নিরাপত্তার বিষয়ে সাহায্য করতে পারি। জরুরি বিপদে সরাসরি ৯৯৯-এ কল করুন।</p>
          </div>
        )}
        {messages.map((message) => (
          <div className={`chat-message ${message.role === "USER" ? "chat-message-user" : "assistant-message"}`} key={message.id}>
            {message.role === "ASSISTANT" && <span className="assistant-avatar">AI</span>}
            <p>{message.content}</p>
          </div>
        ))}
        {sending && <div className="typing-indicator"><i /><i /><i /> সহকারী উত্তর তৈরি করছে</div>}
      </div>
      {stations.length > 0 && (
        <div className="station-results">
          {stations.map((station) => (
            <article key={`${station.name}-${station.area}`}>
              <strong>{station.name}</strong><span>{station.address} · {station.distance_km} km</span>
              {station.phone && <a href={`tel:${station.phone}`}>{station.phone}</a>}
            </article>
          ))}
        </div>
      )}
      <div className="chat-suggestions">
        {role === "CITIZEN" && <button onClick={askNearby}>◉ নিকটস্থ থানা খুঁজুন</button>}
        {suggestions.map((suggestion) => <button key={suggestion} onClick={() => send(suggestion)}>{suggestion}</button>)}
      </div>
      {role === "CITIZEN" && (
        <div className="emergency-directory">
          <button
            type="button"
            className="directory-toggle"
            aria-expanded={showHotlines}
            onClick={() => setShowHotlines((visible) => !visible)}
          >
            {showHotlines ? "জরুরি নম্বর লুকান" : "বাংলাদেশের জরুরি নম্বর দেখুন"}
          </button>
          {showHotlines && (
            <div className="hotline-list">
              <p>যাচাই বাকি নম্বর বর্তমান নাও হতে পারে। তাৎক্ষণিক বিপদে ৯৯৯-এ কল করুন।</p>
              {hotlines.map((hotline) => (
                <article key={hotline.code}>
                  <span><strong>{hotline.service_name}</strong><small>{hotline.situations}</small></span>
                  <span className="hotline-contact">
                    <a href={`tel:${hotline.phone_number}`}>{hotline.phone_number}</a>
                    <small className={hotline.verified ? "verified-label" : "unverified-label"}>
                      {hotline.verified ? "যাচাইকৃত" : "যাচাই বাকি"}
                    </small>
                    <a className="hotline-source" href={hotline.source_url} target="_blank" rel="noreferrer">উৎস</a>
                  </span>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
      <form className="chat-compose" onSubmit={submit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength="2000"
          placeholder="আপনার প্রশ্ন লিখুন…"
          aria-label="সহকারীকে প্রশ্ন করুন"
        />
        <button className="button button-primary" disabled={sending || !draft.trim()} aria-label="পাঠান">↑</button>
      </form>
      <p className="chat-disclaimer">সাধারণ তথ্য মাত্র — এটি জরুরি সেবা বা আইনি পরামর্শের বিকল্প নয়।</p>
    </section>
  );
}

export default App;
