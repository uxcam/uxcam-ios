## Release checklist

- [ ] `Scripts/validate_repository.sh` passes
- [ ] Version matches `release-metadata.json`, `Package.swift`, and the podspec
- [ ] Checksum was calculated from the exact draft Release asset
- [ ] Draft has exactly one asset named `UXCam.xcframework.zip`
- [ ] Existing tags and published Release assets were not changed
- [ ] CocoaPods publication is intentional for this version
