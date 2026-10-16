plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")   // runs the tutor's Python code (cube/, vision/) inside the app
}

android {
    namespace = "com.reveng26.xrcam"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.cubetutor.phone"   // installs beside the bridge app (com.cubetutor.bridge)
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-phone"
        ndk { abiFilters += "arm64-v8a" }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }

    androidResources {
        noCompress += "onnx"
    }

    // The web page (web/dist) and the cube finder's model, copied in by syncTutorAssets below.
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("tutorAssets"))
}

// The repository this app sits in: the Python code, the built web page and the model come from there,
// so there is one copy of each.
val repo: File = rootDir.parentFile

val syncTutorPython by tasks.registering(Sync::class) {
    into(layout.buildDirectory.dir("tutorPython"))
    from(repo) { include("cube/**/*.py", "vision/**/*.py") }
    from(File(repo, "third_party")) { include("rubikscolorresolver/**/*.py") }
}

val syncTutorAssets by tasks.registering(Sync::class) {
    into(layout.buildDirectory.dir("tutorAssets"))
    from(File(repo, "web/dist")) { into("web") }
    from(File(repo, "models")) { include("cube_pose_v3_256.onnx", "cube_pose_v3_256_int8.onnx", "cube_pose_320.onnx"); into("models") }
    doFirst {
        check(File(repo, "web/dist/index.html").isFile) { "web/dist is missing: run `npm install && npm run build` in web/" }
    }
}

tasks.named("preBuild") { dependsOn(syncTutorPython, syncTutorAssets) }
tasks.matching { it.name.startsWith("merge") && (it.name.endsWith("PythonSources") || it.name.endsWith("Assets")) }
    .configureEach { dependsOn(syncTutorPython, syncTutorAssets) }

chaquopy {
    defaultConfig {
        version = "3.10"   // the newest Python that Chaquopy has an OpenCV build for
        pip {
            install("numpy==1.26.2")
            install("opencv-python==4.5.1.48")
            install("pillow==11.0.0")
        }
    }
    sourceSets {
        getByName("main") { srcDir(layout.buildDirectory.dir("tutorPython")) }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.1")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")   // the cube finder
    implementation("org.nanohttpd:nanohttpd-websocket:2.3.1")                // the page's local server
}
