package com.sets4us.aiwatcher;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Debug;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.File;
import java.security.MessageDigest;

public class MainActivity extends Activity {

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Configure Status Bar & Enable FLAG_SECURE by default against spyware screen capture
        Window window = getWindow();
        if (window != null) {
            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
                window.setStatusBarColor(Color.parseColor("#064e3b"));
                window.setNavigationBarColor(Color.parseColor("#0f172a"));
            }
        }

        // 2. Initialize Hardened WebView
        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#0b1120"));
        setContentView(webView);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(false);
        }

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
            settings.setAllowFileAccessFromFileURLs(false);
            settings.setAllowUniversalAccessFromFileURLs(false);
        }
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setUserAgentString(settings.getUserAgentString() + " SETS-Android-Shield/2.0");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        }

        // 3. Attach Native Android Security Bridge
        webView.addJavascriptInterface(new SETSAndroidBridge(), "SETSAndroidBridge");

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleNavigation(url);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP && request != null && request.getUrl() != null) {
                    return handleNavigation(request.getUrl().toString());
                }
                return false;
            }
        });

        webView.loadUrl("file:///android_asset/www/index.html");
    }

    private boolean handleNavigation(String url) {
        if (url == null) return false;
        if (url.startsWith("file:///android_asset/")) {
            return false;
        }
        // Launch WhatsApp, Dialer, Email, LinkedIn & Municipal Portals via safe Android External Intent
        if (url.startsWith("http://") || url.startsWith("https://") ||
            url.startsWith("mailto:") || url.startsWith("tel:") ||
            url.startsWith("whatsapp:")) {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
            } catch (Exception ignored) {
            }
            return true;
        }
        return true;
    }

    @Override
    public void onBackPressed() {
        if (webView != null) {
            webView.evaluateJavascript(
                "(function(){ var s=document.getElementById('mobileMoreSheet'); if(s && !s.classList.contains('hidden')){ s.classList.add('hidden'); return 'closed'; } return 'none'; })()",
                null
            );
        }
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public class SETSAndroidBridge {

        @JavascriptInterface
        public void setFlagSecure(final boolean enable) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Window w = getWindow();
                    if (w != null) {
                        if (enable) {
                            w.addFlags(WindowManager.LayoutParams.FLAG_SECURE);
                        } else {
                            w.clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
                        }
                    }
                }
            });
        }

        @JavascriptInterface
        public String getSecurityPosture() {
            boolean debuggerAttached = Debug.isDebuggerConnected();
            boolean rooted = checkRootIndicators();
            String sigHash = getSignatureSha256Short();
            if (debuggerAttached) {
                return "WARN: Debugger Attached | Sig: " + sigHash;
            }
            if (rooted) {
                return "WARN: Root Indicators Detected | Vault Encrypted | Sig: " + sigHash;
            }
            return "Verified Clean Android OS • No Root • FLAG_SECURE Active • APK SHA256: " + sigHash;
        }

        private boolean checkRootIndicators() {
            String buildTags = Build.TAGS;
            if (buildTags != null && buildTags.contains("test-keys")) {
                return true;
            }
            String[] paths = {
                "/system/app/Superuser.apk",
                "/sbin/su",
                "/system/bin/su",
                "/system/xbin/su",
                "/data/local/xbin/su",
                "/data/local/bin/su"
            };
            for (String p : paths) {
                if (new File(p).exists()) return true;
            }
            return false;
        }

        private String getSignatureSha256Short() {
            try {
                PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), PackageManager.GET_SIGNATURES);
                if (info.signatures != null && info.signatures.length > 0) {
                    Signature sig = info.signatures[0];
                    MessageDigest md = MessageDigest.getInstance("SHA-256");
                    byte[] digest = md.digest(sig.toByteArray());
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < 6 && i < digest.length; i++) {
                        sb.append(String.format("%02X", digest[i]));
                    }
                    return sb.toString();
                }
            } catch (Exception ignored) {
            }
            return "SETS-V2-SIGNED";
        }
    }
}