import XCTest

/// Drives the real app (and the real iOS keyboard) in the simulator from a list
/// of steps, and saves screenshots. Read by scripts/shots.py through the
/// environment: PHONE_STEPS, PHONE_SHOTS and optionally PHONE_APP.
final class ShellUITests: XCTestCase {
    private var app: XCUIApplication!
    private var out: URL!

    override func setUpWithError() throws {
        continueAfterFailure = true
        // PHONE_APP drives another app instead (web mode: Safari, already open on the prototype).
        if let other = ProcessInfo.processInfo.environment["PHONE_APP"], !other.isEmpty {
            app = XCUIApplication(bundleIdentifier: other)
            app.activate()
        } else {
            app = XCUIApplication()
            app.launchArguments = ["-resetState"]
            app.launch()
        }
        let dir = ProcessInfo.processInfo.environment["PHONE_SHOTS"] ?? NSTemporaryDirectory() + "proto-phone-shots"
        out = URL(fileURLWithPath: dir)
        try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        sleep(3)
    }

    private func shot(_ name: String) {
        let data = XCUIScreen.main.screenshot().pngRepresentation
        try? data.write(to: out.appendingPathComponent("\(name).png"))
    }

    private func point(_ spec: String) -> XCUICoordinate? {
        let p = spec.split(separator: ",").compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
        guard p.count == 2 else { return nil }
        return app.coordinate(withNormalizedOffset: CGVector(dx: p[0], dy: p[1]))
    }

    /// XCUITest does not see focus inside a contenteditable: press the keys instead.
    private func type(_ text: String) {
        for c in text {
            let s = String(c)
            if c == " " { if app.keys["space"].exists { app.keys["space"].tap() }; continue }
            for candidate in [s, s.uppercased(), s.lowercased()] where app.keys[candidate].exists {
                app.keys[candidate].tap()
                break
            }
        }
    }

    func testSteps() throws {
        let raw = ProcessInfo.processInfo.environment["PHONE_STEPS"] ?? "shot:launch"
        for step in raw.split(separator: ";").map({ $0.trimmingCharacters(in: .whitespaces) }) where !step.isEmpty {
            let parts = step.split(separator: ":", maxSplits: 1).map(String.init)
            let arg = parts.count > 1 ? parts[1] : ""
            switch parts[0] {
            case "shot": shot(arg.isEmpty ? "shot" : arg)
            case "wait": sleep(UInt32(Double(arg) ?? 1))
            case "swipedown": app.swipeDown(velocity: .fast)
            case "type": type(arg)
            case "tap":
                if arg.hasPrefix("@") {
                    let el = app.descendants(matching: .any)[String(arg.dropFirst())].firstMatch
                    XCTAssertTrue(el.waitForExistence(timeout: 5), "no control labelled \(arg)")
                    el.tap()
                } else if let c = point(arg) {
                    c.tap()
                } else {
                    XCTFail("bad tap step: \(step)")
                }
            default: XCTFail("unknown step: \(step)")
            }
        }
    }
}
