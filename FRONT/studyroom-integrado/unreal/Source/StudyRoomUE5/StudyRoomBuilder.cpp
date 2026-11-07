#include "StudyRoomBuilder.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "TimerManager.h"
#include "Engine/World.h"
#include "UObject/UObjectGlobals.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Guid.h"

namespace StudyRoomMaterials
{
    FLinearColor Fallback(const FString& Key)
    {
        if (Key == TEXT("Wall")) return FLinearColor(0.68f, 0.73f, 0.72f);
        if (Key == TEXT("Accent")) return FLinearColor(0.16f, 0.31f, 0.30f);
        if (Key == TEXT("Floor")) return FLinearColor(0.32f, 0.23f, 0.16f);
        if (Key == TEXT("Wood")) return FLinearColor(0.48f, 0.33f, 0.22f);
        if (Key == TEXT("Dark")) return FLinearColor(0.05f, 0.075f, 0.087f);
        if (Key == TEXT("Fabric")) return FLinearColor(0.24f, 0.29f, 0.31f);
        if (Key == TEXT("LightFabric")) return FLinearColor(0.68f, 0.61f, 0.50f);
        if (Key == TEXT("White")) return FLinearColor(0.90f, 0.85f, 0.72f);
        if (Key == TEXT("Green")) return FLinearColor(0.12f, 0.32f, 0.19f);
        if (Key == TEXT("Ceramic")) return FLinearColor(0.63f, 0.43f, 0.32f);
        if (Key == TEXT("Screen")) return FLinearColor(0.035f, 0.14f, 0.19f);
        if (Key == TEXT("Sky")) return FLinearColor(0.31f, 0.57f, 0.68f);
        if (Key == TEXT("Art")) return FLinearColor(0.72f, 0.44f, 0.28f);
        return FLinearColor(0.5f, 0.5f, 0.5f);
    }
}

AStudyRoomBuilder::AStudyRoomBuilder()
{
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);
}

void AStudyRoomBuilder::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    // Visible al arrastrar StudyRoomBuilder en el editor, sin pulsar Play.
    RebuildRoom();
}

void AStudyRoomBuilder::BeginPlay()
{
    Super::BeginPlay();
    FFileHelper::LoadFileToString(BridgeRoomKey, *FPaths::Combine(FPaths::ProjectDir(), TEXT("room-key.local.txt")));
    BridgeRoomKey.TrimStartAndEndInline();
    UpdateLights();
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(SyncTimer, this, &AStudyRoomBuilder::PollWebSettings, 2.0f, true, 0.5f);
    }
}

void AStudyRoomBuilder::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    // Mejor esfuerzo; cerrar abruptamente el proceso no garantiza entregar este evento.
    if (bIntegratedMode && !CurrentSessionId.IsEmpty() && (CurrentActivityState == TEXT("activa") || CurrentActivityState == TEXT("pausada")) && !bConfirmPending)
        SendActivityConfirmation(TEXT("interrumpida"), FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens));
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(SyncTimer);
    Super::EndPlay(EndPlayReason);
}

void AStudyRoomBuilder::ClearRoom()
{
    for (UActorComponent* C : GeneratedComponents)
    {
        if (IsValid(C)) C->DestroyComponent();
    }
    GeneratedComponents.Empty();
    AdjustableLights.Empty();
}

UStaticMeshComponent* AStudyRoomBuilder::Shape(const FString& Name, const TCHAR* AssetPath, FVector Pos,
     FVector Scale, const FString& MaterialKey, bool bCollision, FRotator Rotation)
{
    UStaticMesh* MeshAsset = LoadObject<UStaticMesh>(nullptr, AssetPath);
    if (!MeshAsset) return nullptr;
    FName Unique = MakeUniqueObjectName(this, UStaticMeshComponent::StaticClass(), FName(*Name));
    UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this, Unique, RF_Transactional);
    C->SetupAttachment(SceneRoot);
    C->SetStaticMesh(MeshAsset);
    C->SetRelativeLocation(Pos);
    C->SetRelativeRotation(Rotation);
    C->SetRelativeScale3D(Scale);
    C->SetMobility(EComponentMobility::Movable);
    C->SetCollisionEnabled(bCollision ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
    // Materiales .uasset generados por Scripts/setup_materials.py, con respaldo visual si faltan.
    const FString Path = FString::Printf(TEXT("/Game/StudyRoom/Materials/M_%s.M_%s"), *MaterialKey, *MaterialKey);
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, *Path);
    if (Material)
    {
        C->SetMaterial(0, Material);
    }
    else
    {
        UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
        if (Base)
        {
            UMaterialInstanceDynamic* D = UMaterialInstanceDynamic::Create(Base, this);
            if (D)
            {
                D->SetVectorParameterValue(TEXT("Color"), StudyRoomMaterials::Fallback(MaterialKey));
                C->SetMaterial(0, D);
            }
        }
    }
    AddInstanceComponent(C);
    C->RegisterComponent();
    GeneratedComponents.Add(C);
    return C;
}

UStaticMeshComponent* AStudyRoomBuilder::Box(const FString& Name, FVector Pos, FVector Scale, const FString& Mat, bool Coll, FRotator Rot)
{
    return Shape(Name, TEXT("/Engine/BasicShapes/Cube.Cube"), Pos, Scale, Mat, Coll, Rot);
}
UStaticMeshComponent* AStudyRoomBuilder::Sphere(const FString& Name, FVector Pos, FVector Scale, const FString& Mat, bool Coll)
{
    return Shape(Name, TEXT("/Engine/BasicShapes/Sphere.Sphere"), Pos, Scale, Mat, Coll);
}
UStaticMeshComponent* AStudyRoomBuilder::Cylinder(const FString& Name, FVector Pos, FVector Scale, const FString& Mat, bool Coll)
{
    return Shape(Name, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"), Pos, Scale, Mat, Coll);
}
UPointLightComponent* AStudyRoomBuilder::PointLight(const FString& Name, FVector Pos, float Intensity, FLinearColor Tint, float Radius, bool bShadows)
{
    UPointLightComponent* Light = NewObject<UPointLightComponent>(this, MakeUniqueObjectName(this, UPointLightComponent::StaticClass(), FName(*Name)), RF_Transactional);
    Light->SetupAttachment(SceneRoot);
    Light->SetRelativeLocation(Pos);
    Light->SetMobility(EComponentMobility::Movable);
    Light->SetIntensity(Intensity);
    Light->SetLightColor(Tint);
    Light->SetAttenuationRadius(Radius);
    Light->SetSourceRadius(16.f);
    Light->SetCastShadows(bShadows);
    AddInstanceComponent(Light);
    Light->RegisterComponent();
    GeneratedComponents.Add(Light);
    AdjustableLights.Add(Light);
    return Light;
}

void AStudyRoomBuilder::AddArchitecture()
{
    const float HW = RoomWidth * .5f, HD = RoomDepth * .5f, H = WallHeight;
    Box(TEXT("Base_Concrete"), FVector(0,0,-21), FVector(RoomWidth/100.f,RoomDepth/100.f,.4f), TEXT("Dark"));
    Box(TEXT("Floor_Base"), FVector(0,0,-5), FVector(RoomWidth/100.f,RoomDepth/100.f,.12f), TEXT("Floor"));
    // Tablones con ligeras juntas reales para dar volumen al piso.
    const int32 Planks = FMath::Max(8, FMath::RoundToInt(RoomWidth/65.f));
    for (int32 i=0; i<Planks; ++i)
    {
        const float PW = RoomWidth / Planks;
        Box(FString::Printf(TEXT("Floor_Plank_%02d"),i), FVector(-HW+PW*(i+.5f),0,2),
            FVector((PW-1.3f)/100.f,RoomDepth/100.f,.05f), i%3==0 ? TEXT("Wood") : TEXT("Floor"));
    }
    Box(TEXT("Wall_Back"), FVector(0,HD,H*.5f), FVector(RoomWidth/100.f,.17f,H/100.f), TEXT("Wall"));
    Box(TEXT("Wall_Left"), FVector(-HW,0,H*.5f), FVector(.17f,RoomDepth/100.f,H/100.f), TEXT("Wall"));
    Box(TEXT("Wall_Right"), FVector(HW,0,H*.5f), FVector(.17f,RoomDepth/100.f,H/100.f), TEXT("Accent"));
    // Frente abierto: más cómodo para observar y editar en el viewport.
    Box(TEXT("Ceiling"), FVector(0,0,H+8), FVector(RoomWidth/100.f,RoomDepth/100.f,.13f), TEXT("White"),false);
    Box(TEXT("Skirting_Back"), FVector(0,HD-12,8), FVector(RoomWidth/100.f,.07f,.16f), TEXT("White"));
    Box(TEXT("Skirting_Left"), FVector(-HW+12,0,8), FVector(.07f,RoomDepth/100.f,.16f), TEXT("White"));
    Box(TEXT("Skirting_Right"), FVector(HW-12,0,8), FVector(.07f,RoomDepth/100.f,.16f), TEXT("Wood"));
    Box(TEXT("Crown_Back"), FVector(0,HD-12,H-8), FVector(RoomWidth/100.f,.12f,.12f), TEXT("White"));
    Box(TEXT("Crown_Right"), FVector(HW-12,0,H-8), FVector(.12f,RoomDepth/100.f,.12f), TEXT("White"));
    // Paneles decorativos laterales con relieve, mejor que una pared plana.
    for (int32 i=0; i<7; ++i)
    {
        const float Y = -HD+105+i*(RoomDepth-210)/6.f;
        Box(FString::Printf(TEXT("Slat_%d"),i), FVector(HW-19,Y,156), FVector(.06f,.095f,2.35f), TEXT("Wood"));
    }
    // Ventana con marco físico, cielo y un umbral; el panel es escenográfico.
    const float WX = -HW*.34f;
    Box(TEXT("Window_View"), FVector(WX,HD-18,174), FVector(3.6f,.06f,1.7f), TEXT("Sky"),false);
    Box(TEXT("Window_Top"), FVector(WX,HD-24,265), FVector(3.85f,.13f,.09f), TEXT("Dark"));
    Box(TEXT("Window_Bottom"), FVector(WX,HD-24,83), FVector(3.85f,.17f,.11f), TEXT("White"));
    Box(TEXT("Window_Left"), FVector(WX-190,HD-24,174), FVector(.095f,.13f,1.8f), TEXT("Dark"));
    Box(TEXT("Window_Right"), FVector(WX+190,HD-24,174), FVector(.095f,.13f,1.8f), TEXT("Dark"));
    Box(TEXT("Window_Crossbar"), FVector(WX,HD-29,174), FVector(.075f,.12f,1.8f), TEXT("Dark"));
    Box(TEXT("Window_Sill"), FVector(WX,HD-39,78), FVector(4.0f,.32f,.055f), TEXT("Wood"));
}

void AStudyRoomBuilder::AddDeskArea()
{
    const float X = -115.f, Y = 45.f;
    // Alfombra y escritorio amplio con bandejas, cajones, panel de pantalla.
    Box(TEXT("Rug"), FVector(X,-160,5), FVector(4.5f,3.3f,.035f), TEXT("LightFabric"),false);
    Box(TEXT("Rug_Trim"), FVector(X,-160,6), FVector(4.38f,3.18f,.032f), TEXT("Fabric"),false);
    Box(TEXT("Desk_Top"), FVector(X,Y,77), FVector(3.2f,1.45f,.09f), TEXT("Wood"));
    for (int s : {-1,1})
    {
        Box(FString::Printf(TEXT("Desk_Leg_F_%d"),s), FVector(X+s*147,Y-58,36), FVector(.07f,.07f,.7f), TEXT("Dark"));
        Box(FString::Printf(TEXT("Desk_Leg_B_%d"),s), FVector(X+s*147,Y+58,36), FVector(.07f,.07f,.7f), TEXT("Dark"));
    }
    Box(TEXT("Desk_Cabinet"), FVector(X-125,Y+18,45), FVector(.58f,.72f,.58f), TEXT("Wood"));
    for (int i=0; i<3; ++i)
    {
        Box(FString::Printf(TEXT("Drawer_%d"),i), FVector(X-125,Y-21,31+i*15), FVector(.51f,.018f,.105f), TEXT("White"));
        Box(FString::Printf(TEXT("Drawer_Handle_%d"),i), FVector(X-125,Y-23,31+i*15), FVector(.19f,.025f,.017f), TEXT("Dark"));
    }
    Box(TEXT("Monitor_Base"), FVector(X+20,Y+49,83), FVector(.35f,.26f,.025f), TEXT("Dark"));
    Box(TEXT("Monitor_Neck"), FVector(X+20,Y+53,105), FVector(.055f,.055f,.43f), TEXT("Dark"));
    Box(TEXT("Monitor_Frame"), FVector(X+20,Y+56,140), FVector(1.23f,.072f,.76f), TEXT("Dark"));
    Box(TEXT("Monitor_Display"), FVector(X+20,Y+51,140), FVector(1.12f,.016f,.65f), TEXT("Screen"),false);
    Box(TEXT("Monitor_Highlight"), FVector(X+20,Y+49,136), FVector(.72f,.017f,.018f), TEXT("Sky"),false);
    Box(TEXT("Keyboard"), FVector(X,Y-23,84), FVector(.67f,.25f,.04f), TEXT("Dark"));
    Sphere(TEXT("Mouse"), FVector(X+88,Y-19,85), FVector(.1f,.17f,.055f), TEXT("Dark"));
    Cylinder(TEXT("Cup"), FVector(X-79,Y+25,91), FVector(.12f,.12f,.18f), TEXT("Ceramic"));
    // Silla tapizada, brazos y cinco radios; tres tipos de geometría.
    const FVector ChairPos(X+120,Y-180,0);
    Cylinder(TEXT("Chair_Base"), ChairPos+FVector(0,0,11), FVector(.6f,.6f,.055f), TEXT("Dark"));
    Cylinder(TEXT("Chair_Pole"), ChairPos+FVector(0,0,29), FVector(.08f,.08f,.47f), TEXT("Dark"));
    Box(TEXT("Chair_Seat"), ChairPos+FVector(0,0,53), FVector(.87f,.86f,.14f), TEXT("Fabric"));
    Box(TEXT("Chair_Cushion"), ChairPos+FVector(0,-2,61), FVector(.76f,.72f,.055f), TEXT("LightFabric"));
    Box(TEXT("Chair_Back"), ChairPos+FVector(0,40,103), FVector(.88f,.14f,.85f), TEXT("Fabric"),true,FRotator(-8.f,0,0));
    for (int i : {-1,1})
    {
        Box(FString::Printf(TEXT("Chair_Arm_%d"),i), ChairPos+FVector(i*43,0,79), FVector(.07f,.63f,.06f), TEXT("Dark"));
        Box(FString::Printf(TEXT("Chair_Arm_Post_%d"),i), ChairPos+FVector(i*43,20,68), FVector(.06f,.06f,.28f), TEXT("Dark"));
    }
    // Lámpara de escritorio: tronco inclinado y pantalla de cilindro.
    Cylinder(TEXT("DeskLamp_Base"), FVector(X-120,Y+31,87), FVector(.18f,.18f,.035f), TEXT("Dark"));
    Box(TEXT("DeskLamp_Arm"), FVector(X-120,Y+35,113), FVector(.035f,.035f,.55f), TEXT("Dark"),false,FRotator(0,0,16));
    Cylinder(TEXT("DeskLamp_Shade"), FVector(X-114,Y+40,146), FVector(.24f,.24f,.16f), TEXT("White"),false);
}

void AStudyRoomBuilder::AddShelfArea()
{
    const float HW=RoomWidth*.5f, HD=RoomDepth*.5f;
    const float X=HW-135.f, Y=HD-255.f;
    Box(TEXT("Bookcase_Backing"), FVector(X,Y+28,155), FVector(1.68f,.12f,3.02f), TEXT("Wood"));
    for (int s : {-1,1})
        Box(FString::Printf(TEXT("Bookcase_Side_%d"),s), FVector(X+s*80,Y,153), FVector(.09f,.75f,3.06f), TEXT("Dark"));
    for (int row=0; row<5; ++row)
    {
        Box(FString::Printf(TEXT("Shelf_%d"),row), FVector(X,Y,24+row*66), FVector(1.65f,.75f,.065f), TEXT("Wood"));
        for (int col=0; col<6; ++col)
        {
            // Evita un operador ternario anidado propenso a errores de parentesis.
            FString BookColor;
            switch ((col + row) % 4)
            {
                case 0: BookColor = TEXT("Accent"); break;
                case 1: BookColor = TEXT("Art"); break;
                case 2: BookColor = TEXT("LightFabric"); break;
                default: BookColor = TEXT("Fabric"); break;
            }
            const float Height = 26 + ((col*11+row*7)%17);
            Box(FString::Printf(TEXT("Book_%d_%d"),row,col), FVector(X-63+col*24,Y-6,27+row*66+Height*.5f),
                FVector(.16f,.35f,Height/100.f),BookColor);
        }
    }
}

void AStudyRoomBuilder::AddDecorations()
{
    const float HW=RoomWidth*.5f, HD=RoomDepth*.5f;
    Box(TEXT("Wall_Art_Frame"), FVector(HW-18,-HD+205,193), FVector(.09f,2.2f,1.18f), TEXT("Wood"),false);
    Box(TEXT("Wall_Art_Canvas"), FVector(HW-23,-HD+205,193), FVector(.03f,2.02f,1.03f), TEXT("White"),false);
    Sphere(TEXT("Wall_Art_Abstract_1"), FVector(HW-27,-HD+163,210), FVector(.038f,.48f,.30f), TEXT("Accent"),false);
    Sphere(TEXT("Wall_Art_Abstract_2"), FVector(HW-30,-HD+246,170), FVector(.04f,.35f,.32f), TEXT("Art"),false);
    for (int i=0; i<2; ++i)
    {
        const FVector P(i==0 ? -HW+112 : HW-105, i==0 ? HD-120 : -HD+140, 0);
        Cylinder(FString::Printf(TEXT("Plant_Pot_%d"),i), P+FVector(0,0,30), FVector(.28f,.28f,.58f), TEXT("Ceramic"));
        Cylinder(FString::Printf(TEXT("Plant_Stem_%d"),i), P+FVector(0,0,75), FVector(.06f,.06f,.6f), TEXT("Wood"),false);
        for (int j=0; j<6; ++j)
        {
            const float A=2.f*PI*j/6.f;
            Sphere(FString::Printf(TEXT("Plant_Leaf_%d_%d"),i,j), P+FVector(FMath::Cos(A)*25,FMath::Sin(A)*25,87+j%3*13),
                FVector(.28f,.20f,.11f), TEXT("Green"),false);
        }
    }
    // Luz ambiente de techo con luminarias visibles.
    for (int i : {-1,1})
    {
        Cylinder(FString::Printf(TEXT("Pendant_Cable_%d"),i), FVector(i*200,-10,WallHeight-31), FVector(.025f,.025f,.60f), TEXT("Dark"),false);
        Cylinder(FString::Printf(TEXT("Pendant_Diffuser_%d"),i), FVector(i*200,-10,WallHeight-66), FVector(.35f,.35f,.17f), TEXT("White"),false);
    }
    Cylinder(TEXT("Standing_Lamp_Base"), FVector(HW-95,-HD+70,8), FVector(.35f,.35f,.07f),TEXT("Dark"));
    Cylinder(TEXT("Standing_Lamp_Post"), FVector(HW-95,-HD+70,98), FVector(.04f,.04f,1.78f),TEXT("Dark"));
    Cylinder(TEXT("Standing_Lamp_Shade"), FVector(HW-95,-HD+70,195), FVector(.31f,.31f,.39f),TEXT("White"),false);
}

void AStudyRoomBuilder::RebuildRoom()
{
    ClearRoom();
    AddArchitecture();
    AddDeskArea();
    AddShelfArea();
    AddDecorations();
    // Iluminacion equilibrada para PC/VR: la sala no depende de rebotes Lumen.
    // Las luces de relleno sin sombras evitan rincones negros sin aumentar el brillo de las pantallas.
    // Las intensidades tambien se regulan desde React mediante UpdateLights().
    PointLight(TEXT("Ceiling_Key_1"), FVector(-220,-20,WallHeight-90), 4200.f, FLinearColor(1.f,.95f,.88f), 950.f, true);
    PointLight(TEXT("Ceiling_Key_2"), FVector(220,-20,WallHeight-90), 4000.f, FLinearColor(1.f,.95f,.90f), 950.f, false);
    PointLight(TEXT("Window_Daylight"), FVector(-RoomWidth*.27f,RoomDepth*.5f-125,WallHeight-95), 3600.f, FLinearColor(.83f,.91f,1.f), 980.f, false);
    PointLight(TEXT("Desk_Lamp_Light"), FVector(-230,75,144), 650.f, FLinearColor(1.f,.87f,.72f), 360.f, false);
    // Luz ambiental simulada mediante fuentes distribuidas. No emiten sombras duras.
    PointLight(TEXT("Fill_Front_Left"), FVector(-RoomWidth*.30f,-RoomDepth*.25f,185.f), 2600.f, FLinearColor(1.f,.98f,.95f), 1100.f, false);
    PointLight(TEXT("Fill_Front_Right"), FVector(RoomWidth*.30f,-RoomDepth*.25f,185.f), 2600.f, FLinearColor(1.f,.98f,.95f), 1100.f, false);
    PointLight(TEXT("Fill_Rear_Left"), FVector(-RoomWidth*.27f,RoomDepth*.26f,175.f), 2400.f, FLinearColor(.94f,.97f,1.f), 1100.f, false);
    PointLight(TEXT("Fill_Rear_Right"), FVector(RoomWidth*.27f,RoomDepth*.26f,175.f), 2400.f, FLinearColor(.96f,.98f,1.f), 1100.f, false);
    PointLight(TEXT("Fill_Desk_Front"), FVector(-110.f,-160.f,175.f), 1150.f, FLinearColor(1.f,.98f,.94f), 600.f, false);
    PointLight(TEXT("Fill_Back_Wall"), FVector(0.f,RoomDepth*.28f,205.f), 1900.f, FLinearColor(.96f,.98f,1.f), 850.f, false);
    UpdateLights();
}

void AStudyRoomBuilder::UpdateLights()
{
    // Se aplica tambien en VR, donde los cambios bruscos de exposicion resultan molestos.
    const float B = FMath::Clamp(Brightness, .20f, 3.f);
    const bool bCool = LightingPreset.Equals(TEXT("frio"), ESearchCase::IgnoreCase);
    const bool bNeutral = LightingPreset.Equals(TEXT("neutro"), ESearchCase::IgnoreCase);
    const FLinearColor Tone = bCool ? FLinearColor(.78f,.89f,1.f) :
                              bNeutral ? FLinearColor(1.f,.98f,.94f) : FLinearColor(1.f,.90f,.78f);

    // El orden coincide con RebuildRoom. Luz de relleno independiente de las lamparas visibles.
    const float BaseIntensity[] = {4200.f,4000.f,3600.f,650.f,2600.f,2600.f,2400.f,2400.f,1150.f,1900.f};
    const int32 IntensityCount = UE_ARRAY_COUNT(BaseIntensity);
    for (int32 i = 0; i < AdjustableLights.Num(); ++i)
    {
        if (UPointLightComponent* L = AdjustableLights[i])
        {
            const float Baseline = i < IntensityCount ? BaseIntensity[i] : 1500.f;
            if (i < 2)
            {
                L->SetLightColor(Tone);
            }
            else if (i == 3)
            {
                L->SetLightColor(FLinearColor(1.f,.88f,.77f));
            }
            else if (i >= 4)
            {
                // El relleno mantiene un color suave y neutro, incluso en el preset calido.
                L->SetLightColor(bCool ? FLinearColor(.83f,.92f,1.f) :
                                 bNeutral ? FLinearColor(1.f,.99f,.96f) : FLinearColor(1.f,.95f,.87f));
            }
            const float SessionFactor = bSessionActive ? .96f : 1.f;
            const float FillFactor = i >= 4 ? FMath::Clamp(AmbientFill, .15f, 2.0f) : 1.f;
            L->SetIntensity(Baseline * B * SessionFactor * FillFactor);
        }
    }
}

void AStudyRoomBuilder::ApplySceneSettings(float NewBrightness, const FString& NewPreset, bool bNewSessionActive)
{
    Brightness=FMath::Clamp(NewBrightness,.20f,3.f);
    LightingPreset=NewPreset;
    bSessionActive=bNewSessionActive;
    UpdateLights();
}

void AStudyRoomBuilder::PollWebSettings()
{
    if (bRequestPending) return;
    bRequestPending = true;
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> R = FHttpModule::Get().CreateRequest();
    R->SetURL((ApiBaseUrl.EndsWith(TEXT("/")) ? ApiBaseUrl.LeftChop(1) : ApiBaseUrl) + TEXT("/api/vr/state"));
    R->SetVerb(TEXT("GET"));
    if (!BridgeRoomKey.IsEmpty()) R->SetHeader(TEXT("X-Room-Key"), BridgeRoomKey);
    R->SetTimeout(10.0f);
    TWeakObjectPtr<AStudyRoomBuilder> WeakThis(this);
    R->OnProcessRequestComplete().BindLambda([WeakThis](FHttpRequestPtr Request, FHttpResponsePtr Response, bool bSucceeded)
    {
        if (!WeakThis.IsValid()) return;
        AStudyRoomBuilder* Self = WeakThis.Get();
        Self->bRequestPending = false;
        if (!bSucceeded || !Response.IsValid() || Response->GetResponseCode()!=200) return;
        TSharedPtr<FJsonObject> Json;
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
        if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid()) return;
        double Level=1.0;
        FString Preset=TEXT("calido");
        bool Active=false;
        Json->TryGetNumberField(TEXT("brightness"),Level);
        Json->TryGetStringField(TEXT("lightingPreset"),Preset);
        Json->TryGetBoolField(TEXT("sessionActive"),Active);
        Self->ApplySceneSettings(static_cast<float>(Level),Preset,Active);
        FString Mode;
        Json->TryGetStringField(TEXT("mode"), Mode);
        Self->bIntegratedMode = Mode == TEXT("integrado");
        Self->CurrentSessionId.Empty();
        Json->TryGetStringField(TEXT("sesion_id"), Self->CurrentSessionId);
        Self->CurrentActivityState.Empty();
        Json->TryGetStringField(TEXT("estado"), Self->CurrentActivityState);
        const TSharedPtr<FJsonObject>* Command = nullptr;
        if (Self->bIntegratedMode && Json->TryGetObjectField(TEXT("pendiente"), Command) && Command && Command->IsValid())
        {
            FString SessionId;
            (*Command)->TryGetStringField(TEXT("sesion_id"), SessionId);
            if (SessionId == Self->CurrentSessionId)
            {
                (*Command)->TryGetStringField(TEXT("id"), Self->CurrentCommandId);
                (*Command)->TryGetStringField(TEXT("estado"), Self->CurrentCommandState);
                if (Self->bAutoConfirmCommandsWhilePlaying && !Self->bConfirmPending && Self->HasActorBegunPlay())
                    Self->ConfirmActivityState(Self->CurrentCommandState);
            }
        }
        else { Self->CurrentCommandId.Empty(); Self->CurrentCommandState.Empty(); }
    });
    if (!R->ProcessRequest()) bRequestPending = false;
}

void AStudyRoomBuilder::ConfirmActivityState(const FString& State)
{
    if (!bIntegratedMode || CurrentSessionId.IsEmpty() || bConfirmPending) return;
    if (State == CurrentCommandState && !CurrentCommandId.IsEmpty())
        SendActivityConfirmation(State, CurrentCommandId);
    else if (State == TEXT("interrumpida"))
        SendActivityConfirmation(State, FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens));
}

void AStudyRoomBuilder::SendActivityConfirmation(const FString& State, const FString& CommandId)
{
    if (BridgeRoomKey.IsEmpty() || CurrentSessionId.IsEmpty()) return;
    bConfirmPending = true;
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> R = FHttpModule::Get().CreateRequest();
    R->SetURL((ApiBaseUrl.EndsWith(TEXT("/")) ? ApiBaseUrl.LeftChop(1) : ApiBaseUrl) + TEXT("/api/vr/events"));
    R->SetVerb(TEXT("POST"));
    R->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    R->SetHeader(TEXT("X-Room-Key"), BridgeRoomKey);
    R->SetTimeout(10.0f);
    TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
    Data->SetStringField(TEXT("id"), CommandId);
    Data->SetStringField(TEXT("estado"), State);
    Data->SetStringField(TEXT("sesion_id"), CurrentSessionId);
    FString Content;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Content);
    FJsonSerializer::Serialize(Data, Writer);
    R->SetContentAsString(Content);
    const TWeakObjectPtr<AStudyRoomBuilder> WeakThis(this);
    R->OnProcessRequestComplete().BindLambda([WeakThis](FHttpRequestPtr Request, FHttpResponsePtr Response, bool bSucceeded)
    {
        if (!WeakThis.IsValid()) return;
        WeakThis->bConfirmPending = false;
        if (!bSucceeded || !Response.IsValid() || Response->GetResponseCode() != 200)
            UE_LOG(LogTemp, Warning, TEXT("StudyRoom: confirmacion pendiente; comprobar puente/backend. No se cambia a modo local."));
        // El siguiente sondeo aplica exclusivamente el estado confirmado por Python.
    });
    if (!R->ProcessRequest()) bConfirmPending = false;
}
