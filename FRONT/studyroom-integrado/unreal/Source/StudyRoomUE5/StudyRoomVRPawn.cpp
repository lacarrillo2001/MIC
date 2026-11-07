#include "StudyRoomVRPawn.h"
#include "Components/SceneComponent.h"
#include "Camera/CameraComponent.h"
#include "MotionControllerComponent.h"
#include "HeadMountedDisplayFunctionLibrary.h"
#include "HeadMountedDisplayTypes.h"
#include "IXRTrackingSystem.h"

AStudyRoomVRPawn::AStudyRoomVRPawn()
{
    PrimaryActorTick.bCanEverTick = false;
    VRRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VRRoot"));
    SetRootComponent(VRRoot);
    HmdCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("HmdCamera"));
    HmdCamera->SetupAttachment(VRRoot);
    HmdCamera->bLockToHmd = true;
    LeftController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("LeftController"));
    LeftController->SetupAttachment(VRRoot);
    LeftController->SetTrackingMotionSource(FName(TEXT("Left")));
    RightController = CreateDefaultSubobject<UMotionControllerComponent>(TEXT("RightController"));
    RightController->SetupAttachment(VRRoot);
    RightController->SetTrackingMotionSource(FName(TEXT("Right")));
}

void AStudyRoomVRPawn::BeginPlay()
{
    Super::BeginPlay();
    UHeadMountedDisplayFunctionLibrary::SetTrackingOrigin(EHMDTrackingOrigin::LocalFloor);
}
