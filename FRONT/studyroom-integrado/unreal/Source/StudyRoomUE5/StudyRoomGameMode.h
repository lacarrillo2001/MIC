#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "StudyRoomGameMode.generated.h"

UCLASS()
class STUDYROOMUE5_API AStudyRoomGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AStudyRoomGameMode();
    virtual void BeginPlay() override;
};