import UIKit
import WebKit
import ObjectiveC

/// Full-screen WKWebView that runs the bundled prototype (Web/index.html).
///
/// Contract with the page (see scripts/adapt.py, which injects the page side):
/// - `:root.app-shell` is set before any page script runs.
/// - The page reaches the safe areas with `env(safe-area-inset-*)`.
/// - While the real iOS keyboard is up the web view is shrunk to the space
///   above it and the page is told through `window.__shell.keyboard(open)`.
/// - The page reports its background color/theme and asks to dismiss the
///   keyboard through the `shell` message handler.
/// - `Web/shell.json` says whether the page scrolls natively ("page") or is
///   exactly one viewport tall and never scrolls itself ("app").
final class WebShellController: UIViewController, WKNavigationDelegate, WKUIDelegate {
    private var webView: WKWebView!
    private var bottomConstraint: NSLayoutConstraint!
    private var offsetObservation: NSKeyValueObservation?
    private var isDark = false
    private var keyboardOpen = false

    override var preferredStatusBarStyle: UIStatusBarStyle { isDark ? .lightContent : .darkContent }

    override func loadView() {
        let root = UIView()
        root.backgroundColor = UIColor(named: "LaunchBackground") ?? .systemBackground
        view = root
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        let content = WKUserContentController()
        content.addUserScript(WKUserScript(source: Self.startScript, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        content.add(WeakMessageHandler(self), name: "shell")

        let config = WKWebViewConfiguration()
        config.userContentController = content
        config.allowsInlineMediaPlayback = true
        config.dataDetectorTypes = []

        webView = WKWebView(frame: .zero, configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.bounces = false
        webView.allowsLinkPreview = false
        webView.navigationDelegate = self
        webView.uiDelegate = self
        #if DEBUG
        if #available(iOS 16.4, *) { webView.isInspectable = true }  // Safari > Develop on the Mac, debug builds only
        #endif

        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        bottomConstraint = webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            bottomConstraint,
        ])

        hideInputAccessory()

        if Self.scrollMode() == "app" {
            // The page is exactly one viewport tall; the document itself never scrolls.
            // WebKit still nudges the main scroll view to reveal a focused field, which
            // lifts the whole app under the keyboard, so pin it back to zero.
            webView.scrollView.isScrollEnabled = false
            offsetObservation = webView.scrollView.observe(\.contentOffset, options: [.new]) { scrollView, _ in
                if scrollView.contentOffset != .zero { scrollView.contentOffset = .zero }
            }
        }

        NotificationCenter.default.addObserver(self, selector: #selector(keyboardWillChangeFrame(_:)),
                                               name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(keyboardWillChangeFrame(_:)),
                                               name: UIResponder.keyboardWillHideNotification, object: nil)

        // UI tests start from the seed data: the prototype may save state in localStorage.
        if ProcessInfo.processInfo.arguments.contains("-resetState") {
            WKWebsiteDataStore.default().removeData(ofTypes: [WKWebsiteDataTypeLocalStorage],
                                                    modifiedSince: .distantPast) { [weak self] in
                self?.loadPage()
            }
        } else {
            loadPage()
        }
    }

    private static func scrollMode() -> String {
        guard let url = Bundle.main.url(forResource: "shell", withExtension: "json", subdirectory: "Web"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let mode = json["scroll"] as? String else { return "page" }
        return mode
    }

    private func loadPage() {
        guard let url = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "Web") else { return }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }

    /// iOS puts a Prev / Next / Done bar above the keyboard for web fields. A
    /// prototype has its own inputs, so the content view is given a subclass
    /// whose inputAccessoryView is nil. Uses a private class name by prefix:
    /// if a future iOS renames it, the bar simply comes back.
    private func hideInputAccessory() {
        guard let content = webView.scrollView.subviews.first(where: { String(describing: type(of: $0)).hasPrefix("WKContent") }) else { return }
        let base: AnyClass = type(of: content)
        let name = "\(base)_NoAccessory"
        var sub: AnyClass? = NSClassFromString(name)
        if sub == nil {
            sub = objc_allocateClassPair(base, name, 0)
            let nothing: @convention(block) (AnyObject) -> AnyObject? = { _ in nil }
            class_addMethod(sub, #selector(getter: UIResponder.inputAccessoryView),
                            imp_implementationWithBlock(nothing), "@@:")
            objc_registerClassPair(sub!)
        }
        object_setClass(content, sub!)
    }

    // MARK: Keyboard

    /// Shrinks the web view to the space above the keyboard. Shrinking (instead of
    /// additionalSafeAreaInsets) is what keeps WebKit from shifting the whole page;
    /// the strip the web view uncovers is painted with the page's own background.
    @objc private func keyboardWillChangeFrame(_ note: Notification) {
        guard let info = note.userInfo,
              let endFrame = (info[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue else { return }
        let keyboard = view.convert(endFrame, from: nil)
        var overlap = note.name == UIResponder.keyboardWillHideNotification ? 0 : max(0, view.bounds.maxY - keyboard.minY)
        if keyboard.height < 1 { overlap = 0 }

        let open = overlap > 0
        if open != keyboardOpen {
            keyboardOpen = open
            webView.evaluateJavaScript("window.__shell&&window.__shell.keyboard(\(open))", completionHandler: nil)
        }

        guard bottomConstraint.constant != -overlap else { return }
        let duration = info[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double ?? 0.25
        let curve = info[UIResponder.keyboardAnimationCurveUserInfoKey] as? UInt ?? 7
        bottomConstraint.constant = -overlap
        UIView.animate(withDuration: duration, delay: 0,
                       options: [UIView.AnimationOptions(rawValue: curve << 16), .beginFromCurrentState]) {
            self.view.layoutIfNeeded()
        }
    }

    // MARK: Page bridge

    fileprivate func receive(_ body: Any) {
        // Only these keys are read, with checked types and ranges; anything else is ignored.
        guard let msg = body as? [String: Any] else { return }
        if let r = msg["r"] as? Double, let g = msg["g"] as? Double, let b = msg["b"] as? Double,
           [r, g, b].allSatisfy({ (0...255).contains($0) }) {
            view.backgroundColor = UIColor(red: r / 255, green: g / 255, blue: b / 255, alpha: 1)
        }
        if let dark = msg["dark"] as? Bool, dark != isDark {
            isDark = dark
            overrideUserInterfaceStyle = dark ? .dark : .light  // keyboard and pickers follow the page theme
            setNeedsStatusBarAppearanceUpdate()
        }
        // The page moved focus off a field without blurring it: a programmatic
        // focus move does not dismiss the real keyboard.
        if msg["endEditing"] as? Bool == true { webView.endEditing(true) }
    }

    // MARK: Navigation
    //
    // The prototype is untrusted code. It may load https subresources (images,
    // fonts, CDNs) but it may only *navigate* inside Web/. A link the person
    // taps to http(s), mailto: or tel: opens outside the app; anything else
    // (other apps' URL schemes, files outside Web/, redirects on load) is refused.

    private var webRoot: URL? {
        Bundle.main.url(forResource: "Web", withExtension: nil)?.standardizedFileURL
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, let scheme = url.scheme?.lowercased() else {
            decisionHandler(.cancel)
            return
        }
        let mainFrame = action.targetFrame?.isMainFrame ?? true
        switch scheme {
        case "file":
            let path = url.standardizedFileURL.resolvingSymlinksInPath().path
            let root = webRoot?.resolvingSymlinksInPath().path ?? "/nonexistent"
            decisionHandler(path == root || path.hasPrefix(root + "/") ? .allow : .cancel)
        case "about", "data", "blob":
            decisionHandler(.allow)  // about:blank, srcdoc and generated content stay in the sandbox
        case "https" where !mainFrame:
            decisionHandler(.allow)  // an embedded https iframe (a map, a video) stays in its frame
        case "http", "https", "mailto", "tel":
            if action.navigationType == .linkActivated || action.targetFrame == nil {
                UIApplication.shared.open(url)
            }
            decisionHandler(.cancel)
        default:
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, ["http", "https", "mailto", "tel"].contains(url.scheme?.lowercased() ?? "") {
            UIApplication.shared.open(url)
        }
        return nil
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        webView.reload()
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        present(alert, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
        present(alert, animated: true)
    }

    // MARK: Injected scripts

    private static let startScript = "document.documentElement.classList.add('app-shell');"
}

/// WKUserContentController retains its handlers; this breaks the cycle.
private final class WeakMessageHandler: NSObject, WKScriptMessageHandler {
    weak var target: WebShellController?
    init(_ target: WebShellController) { self.target = target }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.receive(message.body)
    }
}
