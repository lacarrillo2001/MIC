#include "StudyRoomGameMode.h"
#include "StudyRoomBuilder.h"
#include "StudyRoomCharacter.h"
#include "StudyRoomVRPawn.h"
#include "HeadMountedDisplayFunctionLibrary.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
#include "Engine/World.h"

AStudyRoomGameMode::AStudyRoomGameMode()
{
    // Desktop cuando no hay HMD. En Play con OpenXR activo se cambia al Pawn VR.
    DefaultPawnClass = AStudyRoomCharacter::StaticClass();
}

void AStudyRoomGameMode::BeginPlay()
{
    Super::BeginPlay();
    UWorld* World = GetWorld();
    if (!World) return;
    // Evita duplicar la sala si ya se arrastró StudyRoomBuilder al mapa.
    bool bRoomExists = false;
    for (TActorIterator<AStudyRoomBuilder> It(World); It; ++It)
    {
        bRoomExists = true;
        break;
    }
    if (!bRoomExists)
        World->SpawnActor<AStudyRoomBuilder>(AStudyRoomBuilder::StaticClass(),FVector::ZeroVector,FRotator::ZeroRotator);

    if (UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayConnected() &&
        UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayEnabled())
    {
        if (APlayerController* PC=World->GetFirstPlayerController())
        {
            APawn* OldPawn = PC->GetPawn();
            AStudyRoomVRPawn* VRPawn = World->SpawnActor<AStudyRoomVRPawn>(AStudyRoomVRPawn::StaticClass(),
                FVector(90.f,-290.f,0.f), FRotator(0.f,90.f,0.f));
            if (VRPawn)
            {
                PC->Possess(VRPawn);
                if (OldPawn && OldPawn!=VRPawn) OldPawn->Destroy();
            }
        }
    }
}
