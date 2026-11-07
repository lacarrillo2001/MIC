#include "StudyRoomCharacter.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/InputSettings.h"

AStudyRoomCharacter::AStudyRoomCharacter()
{
    PrimaryActorTick.bCanEverTick = false;
    GetCapsuleComponent()->InitCapsuleSize(42.f, 96.f);
    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0.f, 0.f, 64.f));
    FirstPersonCamera->bUsePawnControlRotation = true;
    bUseControllerRotationYaw = true;
    GetCharacterMovement()->MaxWalkSpeed = 360.f;
}

void AStudyRoomCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxis("MoveForward", this, &AStudyRoomCharacter::MoveForward);
    PlayerInputComponent->BindAxis("MoveRight", this, &AStudyRoomCharacter::MoveRight);
    PlayerInputComponent->BindAxis("Turn", this, &APawn::AddControllerYawInput);
    PlayerInputComponent->BindAxis("LookUp", this, &APawn::AddControllerPitchInput);
}

void AStudyRoomCharacter::MoveForward(float Value)
{
    if (Controller && !FMath::IsNearlyZero(Value))
        AddMovementInput(GetActorForwardVector(), Value);
}
void AStudyRoomCharacter::MoveRight(float Value)
{
    if (Controller && !FMath::IsNearlyZero(Value))
        AddMovementInput(GetActorRightVector(), Value);
}