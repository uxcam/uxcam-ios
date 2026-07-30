# UXCamWrapper

Swift Package Manager binary targets cannot declare linker settings. This small
source target carries the Apple framework and system library linker settings
required by the `UXCam` binary target.

Applications should depend on the `UXCam` product, not this target directly.
