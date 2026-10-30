import Foundation
import Security

// Pass the credential only through the inherited environment, never argv or a file.
guard let value = ProcessInfo.processInfo.environment["ODDS_API_KEY"], !value.isEmpty else {
    fputs("ODDS_API_KEY is missing\n", stderr)
    exit(1)
}
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "com.ncoprod.closing-line-lab.ODDS_API_KEY",
    kSecAttrAccount as String: NSUserName()
]
let attributes = [kSecValueData as String: Data(value.utf8)]
var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
if status == errSecItemNotFound {
    status = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
}
guard status == errSecSuccess else {
    fputs("Keychain storage failed (status \(status))\n", stderr)
    exit(1)
}
print("Credential stored in login Keychain")
