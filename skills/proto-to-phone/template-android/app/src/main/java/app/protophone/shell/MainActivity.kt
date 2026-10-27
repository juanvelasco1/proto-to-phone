package app.protophone.shell

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Message
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewClientCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import org.json.JSONObject
import kotlin.math.max

/**
 * Full-screen WebView that runs the bundled prototype (assets/web/index.html).
 *
 * Same contract as the iOS shell (see scripts/adapt.py and assets/shell.js):
 * - The page is served from https://appassets.androidplatform.net/assets/ by
 *   WebViewAssetLoader; file and content access are off.
 * - The root view is padded by the system bars, the display cutout and the
 *   keyboard, so the page never sits under them; the page is told when the
 *   keyboard opens through window.__shell.keyboard(open).
 * - The page reports its background color/theme and asks to close the keyboard
 *   through the "protoShell" web message listener, limited to the asset origin.
 * - The prototype is untrusted: it may only navigate inside its own assets.
 */
class MainActivity : ComponentActivity() {
    private lateinit var root: FrameLayout
    private lateinit var web: WebView
    private var keyboardOpen = false
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val pickFiles = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data))
        fileCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)  // chrome://inspect, debug builds only

        root = FrameLayout(this)
        root.setBackgroundColor(Color.WHITE)
        web = WebView(this)
        root.addView(web, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        setContentView(root)

        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, max(bars.bottom, ime.bottom))
            val open = insets.isVisible(WindowInsetsCompat.Type.ime())
            if (open != keyboardOpen) {
                keyboardOpen = open
                web.evaluateJavascript("window.__shell&&window.__shell.keyboard($open)", null)
            }
            WindowInsetsCompat.CONSUMED
        }

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportMultipleWindows(true)  // window.open / target=_blank reach onCreateWindow
            textZoom = 100
        }

        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        web.webViewClient = object : WebViewClientCompat() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                loader.shouldInterceptRequest(request.url)

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                if (url.scheme == "https" && url.host == ASSET_HOST) return false  // inside the prototype
                if (!request.isForMainFrame) return url.scheme != "https"         // https iframes stay in their frame
                if (request.hasGesture() && url.scheme in OUTSIDE) openOutside(url)  // a tapped link
                return true                                                        // anything else: refused
            }
        }

        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams,
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                return try {
                    pickFiles.launch(params.createIntent())
                    true
                } catch (e: ActivityNotFoundException) {
                    fileCallback = null
                    false
                }
            }

            /** target=_blank or window.open after a tap: read the URL and open it outside the app. */
            override fun onCreateWindow(view: WebView, isDialog: Boolean, isUserGesture: Boolean, resultMsg: Message): Boolean {
                if (!isUserGesture) return false
                val probe = WebView(this@MainActivity)
                probe.webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean {
                        if (r.url.scheme in OUTSIDE) openOutside(r.url)
                        v.destroy()
                        return true
                    }
                }
                (resultMsg.obj as WebView.WebViewTransport).webView = probe
                resultMsg.sendToTarget()
                return true
            }
        }

        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "protoShell", setOf("https://$ASSET_HOST")) { _, message, _, isMainFrame, _ ->
                if (isMainFrame) message.data?.let { receive(it) }
            }
        }

        web.loadUrl("https://$ASSET_HOST/assets/web/index.html")
    }

    /** Only these keys are read, with checked types and ranges; anything else is ignored. */
    private fun receive(data: String) {
        val msg = try { JSONObject(data) } catch (e: Exception) { return }
        if (msg.has("r") && msg.has("g") && msg.has("b")) {
            val r = msg.optInt("r", -1)
            val g = msg.optInt("g", -1)
            val b = msg.optInt("b", -1)
            if (listOf(r, g, b).all { it in 0..255 }) root.setBackgroundColor(Color.rgb(r, g, b))
        }
        if (msg.has("dark")) {
            val light = !msg.optBoolean("dark", false)
            WindowCompat.getInsetsController(window, root).apply {
                isAppearanceLightStatusBars = light
                isAppearanceLightNavigationBars = light
            }
        }
        if (msg.optBoolean("endEditing", false)) {
            WindowCompat.getInsetsController(window, root).hide(WindowInsetsCompat.Type.ime())
            web.clearFocus()
        }
    }

    private fun openOutside(url: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, url).addCategory(Intent.CATEGORY_BROWSABLE))
        } catch (e: ActivityNotFoundException) {
            // nothing on the phone handles it: ignore, like a dead link
        }
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    private companion object {
        const val ASSET_HOST = "appassets.androidplatform.net"
        val OUTSIDE = setOf("http", "https", "mailto", "tel")
    }
}
