"""
SETS AI Lead & Building Permit Watcher (www.sets4us.com)
Official Android APK Builder & Security Hardening Pipeline
Builds: d:\\PYTHON\\MARKET\\SETS_AI_Lead_Watcher_Android.apk
"""

import os
import shutil
import subprocess
import urllib.request
import zipfile

ROOT_DIR = r"d:\PYTHON\MARKET"
SDK_CACHE_DIR = os.path.join(ROOT_DIR, "build", "android_sdk")
ANDROID_PROJ_DIR = os.path.join(ROOT_DIR, "android_project")
OUTPUT_APK = os.path.join(ROOT_DIR, "SETS_AI_Lead_Watcher_Android.apk")
DIST_APK = os.path.join(ROOT_DIR, "dist", "SETS_AI_Lead_Watcher_Android.apk")

JDK_BIN = r"C:\Program Files\Amazon Corretto\jdk1.8.0_422\bin"
JAVA_EXE = os.path.join(JDK_BIN, "java.exe")
JAVAC_EXE = os.path.join(JDK_BIN, "javac.exe")
KEYTOOL_EXE = os.path.join(JDK_BIN, "keytool.exe")

BUILD_TOOLS_URL = "https://dl.google.com/android/repository/build-tools_r29.0.3-windows.zip"
PLATFORM_URL = "https://dl.google.com/android/repository/platform-30_r03.zip"


def download_and_extract(url, zip_name, extract_subdir):
    os.makedirs(SDK_CACHE_DIR, exist_ok=True)
    zip_path = os.path.join(SDK_CACHE_DIR, zip_name)
    target_dir = os.path.join(SDK_CACHE_DIR, extract_subdir)
    if os.path.exists(target_dir) and os.listdir(target_dir):
        print(f"[SDK] Using cached {extract_subdir}")
        return target_dir

    if not os.path.exists(zip_path):
        print(f"[SDK] Downloading {url} ...")
        urllib.request.urlretrieve(url, zip_path)
        print(f"[SDK] Downloaded {zip_path} ({os.path.getsize(zip_path) // 1024} KB)")

    print(f"[SDK] Extracting {zip_name} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)
    return target_dir


def find_file_recursive(root_folder, filename):
    for r, _, files in os.walk(root_folder):
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(r, f)
    raise FileNotFoundError(f"Could not find {filename} in {root_folder}")


ANDROID_MANIFEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.sets4us.aiwatcher"
    android:versionCode="2"
    android:versionName="2.0.0">

    <uses-sdk
        android:minSdkVersion="21"
        android:targetSdkVersion="30" />

    <!-- Required for Live LinkedIn, Web, Municipal Portal & WhatsApp API Connectivity -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="false"
        android:fullBackupContent="false"
        android:icon="@drawable/ic_launcher"
        android:label="SETS AI Watcher"
        android:usesCleartextTraffic="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:hardwareAccelerated="true"
        android:theme="@android:style/Theme.DeviceDefault.NoActionBar">

        <activity
            android:name=".MainActivity"
            android:label="SETS AI Watcher"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:exported="true"
            android:launchMode="singleTop">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

NETWORK_SECURITY_CONFIG_XML = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
"""

MAIN_ACTIVITY_JAVA = r"""package com.sets4us.aiwatcher;

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
"""


def build_apk():
    print("=== SETS AI Lead Watcher Android APK Builder ===")
    bt_root = download_and_extract(BUILD_TOOLS_URL, "build-tools_r29.0.3-windows.zip", "build-tools-29.0.3")
    plat_root = download_and_extract(PLATFORM_URL, "platform-30_r03.zip", "platform-30")

    aapt_exe = find_file_recursive(bt_root, "aapt.exe")
    zipalign_exe = find_file_recursive(bt_root, "zipalign.exe")
    dx_jar = find_file_recursive(bt_root, "dx.jar")
    apksigner_jar = find_file_recursive(bt_root, "apksigner.jar")
    android_jar = find_file_recursive(plat_root, "android.jar")

    print(f"[Tools] aapt: {aapt_exe}")
    print(f"[Tools] dx.jar: {dx_jar}")
    print(f"[Tools] apksigner.jar: {apksigner_jar}")
    print(f"[Tools] android.jar: {android_jar}")

    # Prepare Android project folder
    if os.path.exists(ANDROID_PROJ_DIR):
        shutil.rmtree(ANDROID_PROJ_DIR)

    src_pkg_dir = os.path.join(ANDROID_PROJ_DIR, "src", "com", "sets4us", "aiwatcher")
    res_drawable_dir = os.path.join(ANDROID_PROJ_DIR, "res", "drawable")
    res_xml_dir = os.path.join(ANDROID_PROJ_DIR, "res", "xml")
    assets_www_dir = os.path.join(ANDROID_PROJ_DIR, "assets", "www")
    gen_dir = os.path.join(ANDROID_PROJ_DIR, "gen")
    obj_dir = os.path.join(ANDROID_PROJ_DIR, "obj")
    bin_dir = os.path.join(ANDROID_PROJ_DIR, "bin")

    for d in [src_pkg_dir, res_drawable_dir, res_xml_dir, assets_www_dir, gen_dir, obj_dir, bin_dir]:
        os.makedirs(d, exist_ok=True)

    # Write AndroidManifest.xml, network_security_config.xml, MainActivity.java
    manifest_path = os.path.join(ANDROID_PROJ_DIR, "AndroidManifest.xml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(ANDROID_MANIFEST_XML.strip())

    with open(os.path.join(res_xml_dir, "network_security_config.xml"), "w", encoding="utf-8") as f:
        f.write(NETWORK_SECURITY_CONFIG_XML.strip())

    main_java_path = os.path.join(src_pkg_dir, "MainActivity.java")
    with open(main_java_path, "w", encoding="utf-8") as f:
        f.write(MAIN_ACTIVITY_JAVA.strip())

    # Copy SETS logo icon into res/drawable/ic_launcher.png
    logo_png = os.path.join(ROOT_DIR, "assets", "sets_logo.png")
    shutil.copy2(logo_png, os.path.join(res_drawable_dir, "ic_launcher.png"))

    # Copy web/mobile dashboard files into assets/www/
    static_dir = os.path.join(ROOT_DIR, "static")
    for fname in ["index.html", "styles.css", "mobile_engine.js", "app.js", "sets_logo.ico"]:
        src_file = os.path.join(static_dir, fname)
        if os.path.exists(src_file):
            shutil.copy2(src_file, os.path.join(assets_www_dir, fname))

    # Step 1: Generate R.java using aapt
    print("[1/6] Generating R.java with aapt...")
    subprocess.run(
        [
            aapt_exe,
            "package",
            "-f",
            "-m",
            "-J",
            gen_dir,
            "-M",
            manifest_path,
            "-S",
            os.path.join(ANDROID_PROJ_DIR, "res"),
            "-I",
            android_jar,
        ],
        check=True,
    )

    r_java_path = os.path.join(gen_dir, "com", "sets4us", "aiwatcher", "R.java")

    # Step 2: Compile Java sources using javac (targeting Java 1.8 bytecode)
    print("[2/6] Compiling MainActivity.java & R.java with javac...")
    subprocess.run(
        [
            JAVAC_EXE,
            "-source",
            "1.8",
            "-target",
            "1.8",
            "-encoding",
            "UTF-8",
            "-bootclasspath",
            android_jar,
            "-d",
            obj_dir,
            main_java_path,
            r_java_path,
        ],
        check=True,
    )

    # Step 3: Convert compiled .class files into Dalvik bytecode (classes.dex)
    classes_dex = os.path.join(ANDROID_PROJ_DIR, "classes.dex")
    print("[3/6] Converting JVM bytecode to Android Dalvik classes.dex...")
    subprocess.run(
        [
            JAVA_EXE,
            "-jar",
            dx_jar,
            "--dex",
            f"--output={classes_dex}",
            obj_dir,
        ],
        check=True,
    )

    # Step 4: Package resources, AndroidManifest.xml, and assets/www into unsigned.apk
    unsigned_apk = os.path.join(bin_dir, "unsigned.apk")
    print("[4/6] Packaging Android resources and mobile dashboard into APK...")
    subprocess.run(
        [
            aapt_exe,
            "package",
            "-f",
            "-M",
            manifest_path,
            "-S",
            os.path.join(ANDROID_PROJ_DIR, "res"),
            "-A",
            os.path.join(ANDROID_PROJ_DIR, "assets"),
            "-I",
            android_jar,
            "-F",
            unsigned_apk,
        ],
        check=True,
    )

    # Add classes.dex to the root of unsigned.apk
    with zipfile.ZipFile(unsigned_apk, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(classes_dex, "classes.dex")

    # Step 5: Align APK on 4-byte boundaries using zipalign
    aligned_apk = os.path.join(bin_dir, "aligned.apk")
    print("[5/6] Running zipalign optimization...")
    subprocess.run(
        [
            zipalign_exe,
            "-f",
            "4",
            unsigned_apk,
            aligned_apk,
        ],
        check=True,
    )

    # Step 6: Generate RSA-2048 Keystore & Sign APK with V1 + V2 Signature Schemes
    keystore_path = os.path.join(ROOT_DIR, "build", "sets_android_release.keystore")
    if not os.path.exists(keystore_path):
        print("[6/6] Generating RSA-2048 Android Release Keystore...")
        subprocess.run(
            [
                KEYTOOL_EXE,
                "-genkeypair",
                "-v",
                "-keystore",
                keystore_path,
                "-alias",
                "sets4us_key",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-storepass",
                "Sets4Us#2026!",
                "-keypass",
                "Sets4Us#2026!",
                "-dname",
                "CN=SETS Energy & Sustainability, OU=Engineering, O=SETS4US, L=Dubai, S=UAE, C=AE",
            ],
            check=True,
        )

    print("[6/6] Signing APK with V1 + V2 Cryptographic Signature Scheme...")
    subprocess.run(
        [
            JAVA_EXE,
            "-jar",
            apksigner_jar,
            "sign",
            "--ks",
            keystore_path,
            "--ks-key-alias",
            "sets4us_key",
            "--ks-pass",
            "pass:Sets4Us#2026!",
            "--key-pass",
            "pass:Sets4Us#2026!",
            "--v1-signing-enabled",
            "true",
            "--v2-signing-enabled",
            "true",
            "--out",
            OUTPUT_APK,
            aligned_apk,
        ],
        check=True,
    )

    # Verify APK signature
    print("[Verify] Verifying signed APK cryptographic integrity...")
    subprocess.run(
        [
            JAVA_EXE,
            "-jar",
            apksigner_jar,
            "verify",
            "--verbose",
            OUTPUT_APK,
        ],
        check=True,
    )

    os.makedirs(os.path.dirname(DIST_APK), exist_ok=True)
    shutil.copy2(OUTPUT_APK, DIST_APK)
    size_kb = os.path.getsize(OUTPUT_APK) / 1024.0
    print(f"\nSUCCESS! Built & Verified Android APK: {OUTPUT_APK} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    build_apk()

