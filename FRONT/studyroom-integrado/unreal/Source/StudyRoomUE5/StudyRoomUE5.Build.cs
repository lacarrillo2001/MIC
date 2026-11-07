using UnrealBuildTool;
public class StudyRoomUE5 : ModuleRules
{
    public StudyRoomUE5(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
            "HTTP", "Json", "JsonUtilities", "HeadMountedDisplay", "XRBase"
        });
    }
}
