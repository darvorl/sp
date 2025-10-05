"use client";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  MapPin,
  Clock,
  CloudRain,
  Thermometer,
  Wind,
  Sun,
  Snowflake,
  AlertTriangle,
} from "lucide-react";
import React from "react";

interface WeatherProbabilities {
  rain?: {
    probability: number;
    avgDays: number;
    maxRecorded: number;
    message: string;
  };
  temperature?: {
    avg: number;
    min: number;
    max: number;
    message: string;
  };
  extreme_rain?: {
    probability: number;
    avgDays: number;
    maxRecorded: number;
    message: string;
  };
  heat_wave?: {
    probability: number;
    avgDays: number;
    maxTemp: number;
    message: string;
  };
  wind?: {
    probability: number;
    avgSpeed: number;
    maxSpeed: number;
    message: string;
  };
  cold?: {
    probability: number;
    avgDays: number;
    minTemp: number;
    message: string;
  };
}

interface ApiResponse {
  location: string;
  date: string;
  time: string;
  probabilities: WeatherProbabilities;
}

export default function Home() {
  const [date, setDate] = React.useState<Date | undefined>(new Date());
  const [time, setTime] = React.useState("12:00");
  const [lat, setLat] = React.useState("-33.4489"); // Santiago por defecto
  const [lon, setLon] = React.useState("-70.6693");
  const [conditions, setConditions] = React.useState<string[]>([
    "rain",
    "temperature",
  ]);
  const [loading, setLoading] = React.useState(false);
  const [results, setResults] = React.useState<ApiResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const conditionOptions = [
    { id: "rain", label: "Lluvia", icon: CloudRain },
    { id: "temperature", label: "Temperatura", icon: Thermometer },
    { id: "extreme_rain", label: "Lluvia Extrema", icon: AlertTriangle },
    { id: "heat_wave", label: "Ola de Calor", icon: Sun },
    { id: "wind", label: "Viento", icon: Wind },
    { id: "cold", label: "Frío Extremo", icon: Snowflake },
  ];

  const handleConditionChange = (conditionId: string, checked: boolean) => {
    if (checked) {
      setConditions((prev) => [...prev, conditionId]);
    } else {
      setConditions((prev) => prev.filter((c) => c !== conditionId));
    }
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLat(position.coords.latitude.toFixed(4));
          setLon(position.coords.longitude.toFixed(4));
        },
        (error) => {
          console.error("Error getting location:", error);
          alert(
            "No se pudo obtener la ubicación. Usando Santiago, Chile por defecto."
          );
        }
      );
    }
  };

  const calculateProbabilities = async () => {
    if (!date) {
      alert("Por favor selecciona una fecha");
      return;
    }

    if (conditions.length === 0) {
      alert("Por favor selecciona al menos una condición climática");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const response = await fetch(
        "http://localhost:5000/api/calculate-probability",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            date: date.toISOString().split("T")[0],
            time: time,
            lat: parseFloat(lat),
            lon: parseFloat(lon),
            conditions: conditions,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }

      const data: ApiResponse = await response.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message || "Error conectando con el servidor");
      console.error("Error:", err);
    } finally {
      setLoading(false);
    }
  };

  const renderProbabilityCard = (
    type: string,
    data: any,
    icon: React.ElementType
  ) => {
    const Icon = icon;
    return (
      <Card key={type} className="p-4">
        <div className="flex items-center gap-3 mb-3">
          <Icon className="h-5 w-5 text-blue-600" />
          <h3 className="font-semibold capitalize">{type.replace("_", " ")}</h3>
        </div>

        {type === "temperature" ? (
          <div className="space-y-2">
            <div className="text-2xl font-bold text-center">{data.avg}°C</div>
            <div className="flex justify-between text-sm text-gray-600">
              <span>Mín: {data.min}°C</span>
              <span>Máx: {data.max}°C</span>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-2xl font-bold text-center">
              {data.probability}%
            </div>
            {data.avgDays && (
              <div className="text-sm text-gray-600 text-center">
                ~{data.avgDays} días/mes
              </div>
            )}
            {data.maxRecorded && (
              <div className="text-xs text-gray-500 text-center">
                Máx registrado: {data.maxRecorded}
                {type === "wind" ? "m/s" : "mm"}
              </div>
            )}
          </div>
        )}

        <div className="mt-3 p-2 bg-blue-50 rounded text-sm text-blue-800">
          {data.message}
        </div>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-gray-900">🛰️ SpaceRain</h1>
          <p className="text-xl text-gray-600">
            Encuentra el mejor día para tu evento con datos de la NASA
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Panel de Configuración */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5" />
                Configuración del Evento
              </CardTitle>
              <CardDescription>
                Selecciona la fecha, ubicación y condiciones climáticas a
                analizar
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Fecha */}
              <div>
                <Label className="text-base font-medium mb-3 block">
                  Fecha del Evento
                </Label>
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={setDate}
                  className="rounded-lg border"
                  disabled={(date) => date < new Date()}
                />
              </div>

              {/* Hora */}
              <div className="space-y-2">
                <Label htmlFor="time" className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Hora del Evento
                </Label>
                <Input
                  id="time"
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                />
              </div>

              {/* Ubicación */}
              <div className="space-y-3">
                <Label className="text-base font-medium">Ubicación</Label>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={getCurrentLocation}
                    className="whitespace-nowrap"
                  >
                    <MapPin className="h-4 w-4 mr-2" />
                    Mi ubicación
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="lat">Latitud</Label>
                    <Input
                      id="lat"
                      type="number"
                      step="0.0001"
                      value={lat}
                      onChange={(e) => setLat(e.target.value)}
                      placeholder="-33.4489"
                    />
                  </div>
                  <div>
                    <Label htmlFor="lon">Longitud</Label>
                    <Input
                      id="lon"
                      type="number"
                      step="0.0001"
                      value={lon}
                      onChange={(e) => setLon(e.target.value)}
                      placeholder="-70.6693"
                    />
                  </div>
                </div>
              </div>

              {/* Condiciones Climáticas */}
              <div className="space-y-3">
                <Label className="text-base font-medium">
                  Condiciones a Analizar
                </Label>
                <div className="grid grid-cols-2 gap-3">
                  {conditionOptions.map(({ id, label, icon: Icon }) => (
                    <div key={id} className="flex items-center space-x-2">
                      <Checkbox
                        id={id}
                        checked={conditions.includes(id)}
                        onCheckedChange={(checked) =>
                          handleConditionChange(id, Boolean(checked))
                        }
                      />
                      <Label
                        htmlFor={id}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <Icon className="h-4 w-4" />
                        {label}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Botón de Análisis */}
              <Button
                onClick={calculateProbabilities}
                disabled={loading || !date || conditions.length === 0}
                className="w-full"
                size="lg"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analizando datos de NASA...
                  </>
                ) : (
                  "🛰️ Analizar con Datos de NASA"
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Panel de Resultados */}
          <div className="space-y-4">
            {error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-red-800">
                    <AlertTriangle className="h-5 w-5" />
                    <span className="font-medium">Error:</span>
                  </div>
                  <p className="text-red-700 mt-1">{error}</p>
                  <p className="text-sm text-red-600 mt-2">
                    Asegúrate de que el backend esté corriendo en puerto 5000
                  </p>
                </CardContent>
              </Card>
            )}

            {results && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-green-700">
                      ✅ Análisis Completado
                    </CardTitle>
                    <CardDescription>
                      Resultados para {results.location} el {results.date} a las{" "}
                      {results.time}
                    </CardDescription>
                  </CardHeader>
                </Card>

                <div className="grid gap-4">
                  {Object.entries(results.probabilities).map(([type, data]) => {
                    const condition = conditionOptions.find(
                      (c) => c.id === type
                    );
                    return renderProbabilityCard(
                      type,
                      data,
                      condition?.icon || CloudRain
                    );
                  })}
                </div>
              </>
            )}

            {!results && !error && !loading && (
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="pt-6 text-center">
                  <div className="text-blue-600 mb-2">
                    <Sun className="h-8 w-8 mx-auto mb-2" />
                  </div>
                  <p className="text-blue-800 font-medium">
                    Configura tu evento y haz clic en "Analizar" para obtener
                    predicciones basadas en datos satelitales de NASA
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
