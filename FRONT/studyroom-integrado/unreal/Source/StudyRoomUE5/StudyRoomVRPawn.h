#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "StudyRoomVRPawn.generated.h"

class UCameraComponent;
class USceneComponent;
class UMotionControllerComponent;

/** Pawn base para PC VR con seguimiento de visor y mandos vía OpenXR.
 *  La locomoción y agarrar objetos se agregan posteriormente con Enhanced Input.
 */
UCLASS()
class STUDYROOMUE5_API AStudyRoomVRPawn : public APawn
{
    GENERATED_BODY()
public:
    AStudyRoomVRPawn();
    virtual void BeginPlay() override;

protected:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VR")
    TObjectPtr<USceneComponent> VRRoot;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VR")
    TObjectPtr<UCameraComponent> HmdCamera;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VR")
    TObjectPtr<UMotionControllerComponent> LeftController;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="VR")
    TObjectPtr<UMotionControllerComponent> RightController;
};
