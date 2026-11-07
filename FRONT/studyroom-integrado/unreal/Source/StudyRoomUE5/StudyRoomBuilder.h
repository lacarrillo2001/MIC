#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "StudyRoomBuilder.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UPointLightComponent;
class UActorComponent;

/** Habitación parametrizable, visible en el editor y controlable desde la API local. */
UCLASS()
class STUDYROOMUE5_API AStudyRoomBuilder : public AActor
{
    GENERATED_BODY()

public:
    AStudyRoomBuilder();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    UFUNCTION(BlueprintCallable, Category="StudyRoom|Web")
    void ApplySceneSettings(float NewBrightness, const FString& NewPreset, bool bNewSessionActive);

    // Puede llamarse desde la actividad/UMG real. Sin comando solo admite interrupción.
    UFUNCTION(BlueprintCallable, Category="StudyRoom|Integration")
    void ConfirmActivityState(const FString& State);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Web")
    FString ApiBaseUrl = TEXT("http://127.0.0.1:8788");

    // Desactivar cuando una tarea específica deba confirmar desde su propio Blueprint.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Integration")
    bool bAutoConfirmCommandsWhilePlaying = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Web", meta=(ClampMin="0.2", ClampMax="3.0"))
    float Brightness = 1.25f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Web")
    FString LightingPreset = TEXT("neutro");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Lighting", meta=(ClampMin="0.15", ClampMax="2.0", ToolTip="Intensidad de las luces de relleno. 1.0 es equilibrado."))
    float AmbientFill = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="StudyRoom|Web")
    bool bSessionActive = false;

    UPROPERTY(EditAnywhere, Category="StudyRoom|Dimensions", meta=(ClampMin="750.0", ClampMax="2000.0"))
    float RoomWidth = 1100.f;

    UPROPERTY(EditAnywhere, Category="StudyRoom|Dimensions", meta=(ClampMin="750.0", ClampMax="1800.0"))
    float RoomDepth = 1000.f;

    UPROPERTY(EditAnywhere, Category="StudyRoom|Dimensions", meta=(ClampMin="260.0", ClampMax="430.0"))
    float WallHeight = 310.f;

private:
    UPROPERTY(VisibleAnywhere, Category="StudyRoom")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UActorComponent>> GeneratedComponents;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UPointLightComponent>> AdjustableLights;

    FTimerHandle SyncTimer;
    bool bRequestPending = false;
    bool bConfirmPending = false;
    bool bIntegratedMode = false;
    FString BridgeRoomKey;
    FString CurrentSessionId;
    FString CurrentActivityState;
    FString CurrentCommandId;
    FString CurrentCommandState;
    void SendActivityConfirmation(const FString& State, const FString& CommandId);

    void RebuildRoom();
    void ClearRoom();
    UStaticMeshComponent* Shape(const FString& Name, const TCHAR* AssetPath, FVector Pos,
         FVector Scale, const FString& MaterialKey, bool bCollision=true, FRotator Rotation=FRotator::ZeroRotator);
    UStaticMeshComponent* Box(const FString& Name, FVector Pos, FVector Scale,
         const FString& MaterialKey, bool bCollision=true, FRotator Rotation=FRotator::ZeroRotator);
    UStaticMeshComponent* Sphere(const FString& Name, FVector Pos, FVector Scale, const FString& Mat, bool bCollision=false);
    UStaticMeshComponent* Cylinder(const FString& Name, FVector Pos, FVector Scale, const FString& Mat, bool bCollision=true);
    UPointLightComponent* PointLight(const FString& Name, FVector Pos, float Intensity, FLinearColor Tint, float Radius, bool bShadows);
    void AddArchitecture();
    void AddDeskArea();
    void AddShelfArea();
    void AddDecorations();
    void UpdateLights();
    void PollWebSettings();
};
