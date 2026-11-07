using UnrealBuildTool;
using System.Collections.Generic;
public class StudyRoomUE5Target : TargetRules
{
    public StudyRoomUE5Target(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("StudyRoomUE5");
    }
}
