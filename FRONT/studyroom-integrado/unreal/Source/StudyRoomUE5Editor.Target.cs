using UnrealBuildTool;
using System.Collections.Generic;
public class StudyRoomUE5EditorTarget : TargetRules
{
    public StudyRoomUE5EditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("StudyRoomUE5");
    }
}
