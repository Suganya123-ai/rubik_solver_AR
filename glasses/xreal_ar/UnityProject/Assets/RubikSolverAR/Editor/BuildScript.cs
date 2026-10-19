using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace RubikSolverAR.EditorTools
{
    /// <summary>
    /// Command-line (and in-Editor) Android build entry point.
    ///
    /// Command-line usage, on a machine with Unity + Android Build Support +
    /// NRSDK already installed and this project opened at least once (so
    /// Android is the active build target and Player Settings are
    /// configured per the NRSDK sample you based this on):
    ///
    ///   "<UnityPath>/Unity" -batchmode -quit -projectPath /path/to/project \
    ///     -buildTarget Android -executeMethod RubikSolverAR.EditorTools.BuildScript.BuildApk
    ///
    /// Optional arguments:
    ///   -apkOutput <path>      Where to write the APK. Default: Builds/Android/RubikSolverAR.apk
    ///                          (relative to the project root).
    ///   -sceneList <a;b;c>     Semicolon-separated scene paths to build, in order.
    ///                          Default: the enabled scenes in File > Build Settings.
    ///
    /// Optional keystore signing via environment variables (falls back to
    /// Unity's default debug keystore if any are missing -- fine for
    /// sideloading to a developer-registered phone, not for a Play Store
    /// release build):
    ///   ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASS, ANDROID_KEY_ALIAS, ANDROID_KEY_PASS
    ///
    /// This scaffold ships with no .unity scene file (binary Unity assets
    /// aren't hand-authorable outside the Editor -- see xreal_ar/README.md).
    /// Build the scene described in the README's "Scene setup" section,
    /// save it, and add it to File > Build Settings (or pass it via
    /// -sceneList) before running this.
    /// </summary>
    public static class BuildScript
    {
        const string DefaultApkOutput = "Builds/Android/RubikSolverAR.apk";

        [MenuItem("Tools/Rubik Solver AR/Build Android APK")]
        public static void BuildApkMenuItem() => BuildApk();

        public static void BuildApk()
        {
            var scenes = ResolveScenes();
            if (scenes.Length == 0)
            {
                Fail(
                    "No scenes to build. Either add your scene(s) in File > Build Settings, or pass " +
                    "-sceneList <path/to/Scene.unity;path/to/Other.unity> on the command line. " +
                    "See xreal_ar/README.md's 'Scene setup' section -- this scaffold ships with no " +
                    ".unity file, since binary Unity assets can't be hand-authored outside the Editor.");
                return;
            }

            string apkOutput = GetArg("-apkOutput", DefaultApkOutput);
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(apkOutput)) ?? ".");

            ApplyKeystoreFromEnvironment();

            var options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = apkOutput,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = BuildOptions.None,
            };

            Debug.Log($"[BuildScript] Building Android APK -> {apkOutput}\nScenes:\n  " + string.Join("\n  ", scenes));

            var report = BuildPipeline.BuildPlayer(options);
            var summary = report.summary;

            if (summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            {
                Fail($"Build did not succeed: {summary.result} ({summary.totalErrors} error(s)). " +
                     "Check the log above for the actual Unity/NRSDK/Android error -- common causes are " +
                     "a missing Android SDK/NDK/JDK, NRSDK not imported, or Player Settings not yet " +
                     "configured for Android (open the project in the Editor once first).");
                return;
            }

            Debug.Log($"[BuildScript] Build succeeded: {summary.outputPath} " +
                      $"({summary.totalSize / (1024 * 1024)} MB, {summary.totalTime})");
        }

        static string[] ResolveScenes()
        {
            string sceneListArg = GetArg("-sceneList", null);
            if (!string.IsNullOrEmpty(sceneListArg))
            {
                return sceneListArg
                    .Split(';')
                    .Select(s => s.Trim())
                    .Where(s => s.Length > 0)
                    .ToArray();
            }

            return EditorBuildSettings.scenes
                .Where(s => s.enabled)
                .Select(s => s.path)
                .ToArray();
        }

        static void ApplyKeystoreFromEnvironment()
        {
            string keystorePath = Environment.GetEnvironmentVariable("ANDROID_KEYSTORE_PATH");
            string keystorePass = Environment.GetEnvironmentVariable("ANDROID_KEYSTORE_PASS");
            string keyAlias = Environment.GetEnvironmentVariable("ANDROID_KEY_ALIAS");
            string keyPass = Environment.GetEnvironmentVariable("ANDROID_KEY_PASS");

            if (string.IsNullOrEmpty(keystorePath) || string.IsNullOrEmpty(keystorePass) ||
                string.IsNullOrEmpty(keyAlias) || string.IsNullOrEmpty(keyPass))
            {
                Debug.Log("[BuildScript] No (complete) keystore env vars found -- signing with Unity's " +
                          "default debug keystore. Fine for sideloading to a dev-registered phone, not " +
                          "for a store release. Set ANDROID_KEYSTORE_PATH/_PASS/_KEY_ALIAS/_KEY_PASS to sign for release.");
                return;
            }

            PlayerSettings.Android.useCustomKeystore = true;
            PlayerSettings.Android.keystoreName = keystorePath;
            PlayerSettings.Android.keystorePass = keystorePass;
            PlayerSettings.Android.keyaliasName = keyAlias;
            PlayerSettings.Android.keyaliasPass = keyPass;
            Debug.Log($"[BuildScript] Signing with keystore: {keystorePath}, alias: {keyAlias}");
        }

        static string GetArg(string name, string defaultValue)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == name) return args[i + 1];
            return defaultValue;
        }

        static void Fail(string message)
        {
            Debug.LogError("[BuildScript] " + message);
            EditorApplication.Exit(1);
        }
    }
}
