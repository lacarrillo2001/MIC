#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "StudyRoomCharacter.generated.h"

class UCameraComponent;

UCLASS()
class STUDYROOMUE5_API AStudyRoomCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    AStudyRoomCharacter();
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
protected:
    UPROPERTY(VisibleAnywhere, Category="Camera")
    TObjectPtr<UCameraComponent> FirstPersonCamera;
private:
    void MoveForward(float Value);
    void MoveRight(float Value);
};